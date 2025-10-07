# gh-cpi - Create GitHub Project Issue

This program creates a GitHub issue, adds it to a GitHub project and sets
project fields.

## Motivation

There are a few GitHub Actions which can create issues and/or add them to
a project (v2), but none of them can set project fields. Unfortunately, GitHub
APIs (both REST and GraphQL) and `gh` CLI does not provide a convenient way to
set project fields due to that they work with IDs instead of values and the
input structure is discriminated over field types.

This tool works out the inconvenience/limitations by issuing queries to find
field IDs and map field values to field value IDs (for select options or
iterations), and then set field values with these IDs.

As a result, you can use the tool on an ad-hoc basis for a given set of Markdown
files on your workstation, or use it on a GitHub Action.

## Installation and Usage

If you are a Nix user and have `flakes` enabled, you can install the tool with:

```sh
nix profile install github:vst/gh-cpi
```

... or directly run it with:

```sh
nix run github:vst/gh-cpi
```

- You can provide the GitHub API token with the `GH_TOKEN` environment variable
  or with the `--token` command line option.
- You can provide the Markdown file with the `GH_CPI_ISSUE_FILE` environment
  variable or with the `--file` command line option.

Finally, if you have a PAT or Classic Token that has appropriate permissions,
you can use the tool in a GitHub Action. Here is an example:

```yaml
on:
  schedule:
    - cron: "15 6 1 * *"

  workflow_dispatch:

name: "Create Monthly Issues"

permissions:
  contents: "read"
  issues: "write"

jobs:
  create:
    runs-on: "ubuntu-latest"
    steps:
      - name: "Checkout Codebase"
        uses: "actions/checkout@v4"

      - name: "Install Nix"
        uses: "DeterminateSystems/nix-installer-action@v16"

      - name: "Install gh-cpi"
        run: "nix profile install github:vst/gh-cpi"

      - name: "Create Issue: Monthly Security Checks"
        run: "gh-cpi"
        env:
          GH_TOKEN: "${{ secrets.CPI_GH_TOKEN }}"
          GH_CPI_ISSUE_FILE: "./issues/monthly-security-checks.md"

      - name: "Create Issue: Monthly Cloud Costs Review"
        run: "gh-cpi"
        env:
          GH_TOKEN: "${{ secrets.CPI_GH_TOKEN }}"
          GH_CPI_ISSUE_FILE: "./issues/monthly-cloud-costs-review.md"
```

## Markdown File

The input is a GitHub API token and a Markdown file with a front matter.
A sample Markdown file is:

```markdown
---
title: "My Issue Title"
owner: "my-organization-or-user"
repository: "my-repo"
project: 1
assignees:
  - "my-assignee"
labels:
  - "label-a"
  - "label-b"
status: "Planned"
iteration: "@next"
size: "medium"
difficulty: "easy"
inception: "2022-06-06"
---

Issue body text in Markdown format.
```

> [!CAUTION]
>
> This tool assumes a very particular GitHub project setup.
>
> I am planning to make this more generic in the future. If you have interest,
> please star the repository and open an issue.

- All front matter fields are required.
- The `project` field is the project number.
- `title` field can contain Python string formatting placeholders. Available
  substitions are:
  - `{current_iteration}` such as `143`
  - `{next_iteration}` such as `144`
  - `{now}` such as `2025-01-02T12:00:00Z`
  - `{today}` such as `2025-01-02`
  - `{tomorrow}` such as `2025-01-03`
  - `{this_week}` such as `2025/w01`
  - `{next_week}` such as `2025/w02`
  - `{this_month}` such as `2025-01`
  - `{next_month}` such as `2025-02`
- If you want to escape the placeholders, use double braces, such as `{{today}}`.
- The project setup is a very particular one:
  - `status` refers to a `SingleSelect` field with name `Status` and with
    following options:
    - `Inbox`
    - `Triage`
    - `Backlog`
    - `Planned`
    - `Active`
    - `Done`
  - `iteration` refers to a `Iteration` field with name `Iteration` with
    weekly iterations starting from `inception` onwards. It can be either
    `@current` or `@next`.
  - `size` refers to a `SingleSelect` field with name `Size` with following options:
    - `small`
    - `medium`
    - `large`
  - `difficulty` refers to a `SingleSelect` field with name `Difficulty` with
    following options:
    - `easy`
    - `medium`
    - `hard`
- You can pass `type` as the issue type as long as:
  - The owner is an organization, and
  - `type` is one of:
    - `Task`
    - `Bug`
    - `Feature`
    - `Epic`
    - `Docs`

## Development

Enter the Nix shell:

```sh
nix develop
```

Run the tests:

```sh
black --check gh-cpi.py
isort --check gh-cpi.py
flake8 gh-cpi.py
mypy gh-cpi.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE)
file.
