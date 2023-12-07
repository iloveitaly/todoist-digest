# Todoist Project Digest

[Todoist](https://mikebian.co/todoist) doesn't have a way to generate a digest of all recent comments in a project created by a specific user. This makes it challenging to see what changed and what requires your action if you are collaborating with someone on a project.

This is a simple project which generates a digest of all comments by a particular user on a particular project.

## Usage

Run this locally using:

```shell
bin/local-digest-html
```

Or run directly:

```shell
poetry run python run.py \
  --last-synced "2023-12-04T15:52:48Z" \
  --target-user user@gmail.com \
  --target-project ProjectName
```

## Development



# TODO

- [ ] hook into <https://github.com/iloveitaly/iloveitaly/blob/main/.github/workflows/follower-notifier.yml>
