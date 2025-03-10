import argparse
import datetime
import json
import os
import subprocess
import sys
from enum import Enum
from typing import Any, Literal

import frontmatter
from pydantic import BaseModel, Field, ValidationError


class StatusEnum(str, Enum):
    inbox = "Inbox"
    todo = "Todo"
    next = "Next"
    current = "Current"
    done = "Done"


class IterationEnum(str, Enum):
    current = "@current"
    next = "@next"


class PriorityEnum(str, Enum):
    one = "1"
    two = "2"
    three = "3"


class SizeEnum(str, Enum):
    small = "S"
    medium = "M"
    large = "L"
    unknown = "?"


class DifficultyEnum(str, Enum):
    easy = "E"
    medium = "M"
    hard = "H"
    unknown = "?"


class Owner(BaseModel):
    id: str
    login: str
    type: Literal["User", "Organization"]

    @classmethod
    def find(cls, token: str, owner: str) -> "Owner | None":
        query = """query($login: String!) {
            owner: repositoryOwner(login: $login) {
                id
                login
                type: __typename
            }
        }"""

        return cls(**gh_gql(token, query, {"login": owner})["data"]["owner"])


class Issue(BaseModel):
    """
    Represents all the necessary information to create a new issue in a GitHub
    repository, add it to a GitHub project, and set the project fields.
    """

    owner: "Owner"
    repository: str
    project: int
    title: str
    body: str
    assignees: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    status: StatusEnum = Field(default=StatusEnum.todo)
    iteration: IterationEnum = Field(default=IterationEnum.current)
    priority: PriorityEnum = Field(default=PriorityEnum.two)
    size: SizeEnum = Field(default=SizeEnum.medium)
    difficulty: DifficultyEnum = Field(default=DifficultyEnum.medium)
    inception: datetime.date = Field(default=datetime.date(2022, 6, 6))

    @property
    def title_rendered(self) -> str:
        now = datetime.datetime.now(datetime.UTC)
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        this_week = now.strftime("%Y/w%U")
        next_week = (now + datetime.timedelta(days=7)).strftime("%Y/w%U")
        this_month = now.strftime("%Y-%m")
        next_month = (now + datetime.timedelta(days=30)).strftime("%Y-%m")

        return self.title.format(
            current_iteration=self.iteration_number_current,
            next_iteration=self.iteration_number_next,
            now=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            today=today.isoformat(),
            tomorrow=tomorrow.isoformat(),
            this_week=this_week,
            next_week=next_week,
            this_month=this_month,
            next_month=next_month,
        )

    @property
    def iteration_title(self) -> str:
        return f"Iteration {self.iteration_number}"

    @property
    def iteration_number(self) -> int:
        if self.iteration == IterationEnum.current:
            return self.iteration_number_current
        else:
            return self.iteration_number_next

    @property
    def iteration_number_current(self) -> int:
        return (datetime.date.today() - self.inception).days // 7

    @property
    def iteration_number_next(self) -> int:
        return self.iteration_number_current + 1

    @classmethod
    def read(cls, token: str, path: str) -> "Issue":
        ## Read the issue file into metadata and content:
        with open(path, "r") as file:
            content = frontmatter.load(file)

        ## Make sure that we have the owner handle:
        if "owner" not in content.metadata:
            sys.stderr.write("Error: 'owner' not found in metadata\n")
            sys.exit(1)

        ## Attempt to find the owner:
        owner = Owner.find(token, content.metadata["owner"])  # type: ignore

        ## Make sure that we have the owner:
        if owner is None:
            sys.stderr.write("Error: owner not found\n")
            sys.exit(1)

        ## Build args:
        args = {
            **content.metadata,
            "owner": owner,
            "body": content.content,
        }

        ## Attempt to build the issue object and return:
        try:
            return cls(**args)  # type: ignore
        except ValidationError as e:
            sys.stderr.write("Error while reading issue file:\n")
            sys.stderr.write(str(e))
            sys.exit(1)


class ProjectInfo(BaseModel):
    id: str
    status: "ProjectOptionsField"
    iteration: "ProjectOptionsField"
    priority: "ProjectOptionsField"
    size: "ProjectOptionsField"
    difficulty: "ProjectOptionsField"


class ProjectOptionsField(BaseModel):
    """
    This applies to both "SingleSelect" and "Iteration" fields.

    Options are represented as a key-value pair of the option name and
    its corresponding ID.
    """

    id: str
    options: dict[str, str]


def get_project_info(token: str, owner: Owner, number: int) -> ProjectInfo:
    ## Define fragments for the GraphQL query:
    fragments = """
        fragment SingleSelect on ProjectV2SingleSelectField {
            id
            options {
                id
                name
            }
        }

        fragment IterationSelect on ProjectV2IterationField {
            id
            configuration {
                options: iterations {
                    id
                    name: title
                }
            }
        }

        fragment ProjectFields on ProjectV2 {
            id
            status: field(name: "Status") {
                ... SingleSelect
            }
            iteration: field(name: "Iteration") {
                ... IterationSelect
            }
            priority: field(name: "Priority") {
                ... SingleSelect
            }
            size: field(name: "Size") {
                ... SingleSelect
            }
            difficulty: field(name: "Difficulty") {
                ... SingleSelect
            }
        }
    """

    ## Define the GraphQL query name as per owner type:
    query_name = "user" if owner.type == "User" else "organization"

    ## Define the query:
    query = f"""
    {fragments}

    query($login: String!, $project: Int!) {{
        owner: {query_name}(login: $login) {{
            projectV2(number: $project) {{
                ... ProjectFields
            }}
        }}
    }}"""

    ## Run the GraphQL query:
    result = gh_gql(token, query, {"login": owner.login, "project": f"{number}"})

    ## Extract the project data:
    data = result["data"]["owner"]["projectV2"]

    ## Function to build options:
    def build_options(field: dict) -> dict[str, str]:
        return {f["name"]: f["id"] for f in field["options"]}

    ## Build and return the ProjectInfo:
    return ProjectInfo(
        **{
            "id": data["id"],
            "status": {
                "id": data["status"]["id"],
                "options": build_options(data["status"]),
            },
            "iteration": {
                "id": data["iteration"]["id"],
                "options": build_options(data["iteration"]["configuration"]),
            },
            "priority": {
                "id": data["priority"]["id"],
                "options": build_options(data["priority"]),
            },
            "size": {
                "id": data["size"]["id"],
                "options": build_options(data["size"]),
            },
            "difficulty": {
                "id": data["difficulty"]["id"],
                "options": build_options(data["difficulty"]),
            },
        }
    )


################
## OPERATIONS ##
################


def create_project_issue(
    *,
    token: str,
    repo: str,
    project_owner: Owner,
    project_number: int,
    title: str,
    body: str,
    assignees: list[str],
    labels: list[str],
    status: str,
    iteration: str,
    priority: str,
    size: str,
    difficulty: str,
) -> str:
    project = get_project_info(token, project_owner, project_number)

    ## Check if field values are valid:
    if status not in project.status.options:
        print(f"Invalid status: {status}")
        sys.exit(1)
    elif iteration not in project.iteration.options:
        print(f"Invalid iteration: {iteration}")
        sys.exit(1)
    elif priority not in project.priority.options:
        print(f"Invalid priority: {priority}")
        sys.exit(1)
    elif size not in project.size.options:
        print(f"Invalid size: {size}")
        sys.exit(1)
    elif difficulty not in project.difficulty.options:
        print(f"Invalid difficulty: {difficulty}")
        sys.exit(1)

    issue_url = create_issue(token, repo, title, body, assignees, labels)
    item_id = add_issue_to_project(token, project_owner, project_number, issue_url)

    set_project_item_field_select(
        token,
        project.id,
        item_id,
        project.status.id,
        project.status.options[status],
    )
    set_project_item_field_iteration(
        token,
        project.id,
        item_id,
        project.iteration.id,
        project.iteration.options[iteration],
    )
    set_project_item_field_select(
        token,
        project.id,
        item_id,
        project.priority.id,
        project.priority.options[priority],
    )
    set_project_item_field_select(
        token,
        project.id,
        item_id,
        project.size.id,
        project.size.options[size],
    )
    set_project_item_field_select(
        token,
        project.id,
        item_id,
        project.difficulty.id,
        project.difficulty.options[difficulty],
    )

    return issue_url


def create_issue(
    token: str,
    repo: str,
    title: str,
    body: str,
    assignees: list[str],
    labels: list[str],
) -> str:
    output = gh(
        token,
        ["issue", "create"],
        [
            ("repo", repo),
            ("title", title),
            ("body", body),
            ("assignee", ",".join(assignees)),
            *[("label", label) for label in labels],
        ],
    )

    return output.strip()


def add_issue_to_project(
    token: str, project_owner: Owner, project_number: int | str, issue_url: str
) -> str:
    output = gh(
        token,
        ["project", "item-add"],
        [
            ("owner", project_owner.login),
            ("url", issue_url),
            ("format", "json"),
        ],
        [],
        [f"{project_number}"],
    )

    return json.loads(output)["id"]


def set_project_item_field_select(
    token: str, project_id: str, item_id: str, field_id: str, option_id: str
) -> None:
    gh(
        token,
        ["project", "item-edit"],
        [
            ("id", item_id),
            ("project-id", project_id),
            ("field-id", field_id),
            ("single-select-option-id", option_id),
        ],
    )


def set_project_item_field_iteration(
    token: str, project_id: str, item_id: str, field_id: str, iteration_id: str
) -> None:
    gh(
        token,
        ["project", "item-edit"],
        [
            ("id", item_id),
            ("project-id", project_id),
            ("field-id", field_id),
            ("iteration-id", iteration_id),
        ],
    )


#############
## HELPERS ##
#############


def gh(
    token: str,
    commands: list[str],
    options: list[tuple[str, str]],
    flags: list[str] = [],
    arguments: list[str] = [],
) -> Any:
    ## Build the base command args:
    args = ["gh", *commands]

    ## Add options to the command args:
    for key, value in options:
        args.extend([f"--{key}", value])

    ## Add flags to the command args:
    for flag in flags:
        args.append(f"--{flag}")

    ## Add additional args to the command:
    for arg in arguments:
        args.append(arg)

    ## Build the environment to run the command inside:
    env = {**os.environ, "GH_TOKEN": token}

    ## Run the command:
    output = subprocess.run(args, env=env, capture_output=True)

    ## Check for errors:
    if output.returncode != 0:
        raise RuntimeError(f"GitHub Interface Error: {output.stderr.decode('utf-8')}")

    ## Return the output:
    return output.stdout.decode("utf-8")


def gh_gql(token: str, query: str, vars: dict[str, str]) -> dict:
    ## Attempt to issue the query:
    output = gh(
        token,
        ["api", "graphql"],
        [
            ("field", f"query={query}"),
            *[("field", f"{key}={value}") for key, value in vars.items()],
        ],
    )

    ## Return the parsed JSON output:
    return json.loads(output)


class EnvDefault(argparse.Action):
    def __init__(self, envvar, required=True, default=None, **kwargs):
        if envvar:
            if envvar in os.environ:
                default = os.environ[envvar]
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


##########
## MAIN ##
##########


def main():
    ## Create the CLI arguments parser:
    parser = argparse.ArgumentParser(
        description="Create a new issue in a GitHub Project"
    )
    parser.add_argument(
        "--token",
        action=EnvDefault,
        envvar="GH_TOKEN",
        required=True,
        help="The GitHub token (env: GH_TOKEN)",
    )
    parser.add_argument(
        "--file",
        action=EnvDefault,
        envvar="GH_CPI_ISSUE_FILE",
        required=True,
        help="The path to the issue file (env: GH_CPI_ISSUE_FILE)",
    )

    ## Parse the CLI arguments:
    args = parser.parse_args()

    ## Read the issue file:
    issue = Issue.read(args.token, args.file)

    ## Create the issue:
    issue_url = create_project_issue(
        token=args.token,
        repo=f"{issue.owner.login}/{issue.repository}",
        project_owner=issue.owner,
        project_number=issue.project,
        title=issue.title_rendered,
        body=issue.body,
        assignees=issue.assignees,
        labels=issue.labels,
        status=issue.status.value,
        iteration=issue.iteration_title,
        priority=issue.priority.value,
        size=issue.size.value,
        difficulty=issue.difficulty.value,
    )

    ## Print the issue URL:
    sys.stdout.write(issue_url)


############
## SCRIPT ##
############


if __name__ == "__main__":
    main()
