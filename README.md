[![Release Notes](https://img.shields.io/github/release/iloveitaly/todoist-digest)](https://github.com/iloveitaly/todoist-digest/releases) [![Downloads](https://static.pepy.tech/badge/todoist-digest/month)](https://pepy.tech/project/todoist-digest) [![Python Versions](https://img.shields.io/pypi/pyversions/todoist-digest)](https://pypi.org/project/todoist-digest) ![GitHub CI Status](https://github.com/iloveitaly/todoist-digest/actions/workflows/build_and_publish.yml/badge.svg) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Todoist Project Digest

[Todoist](https://mikebian.co/todoist) doesn't have a way to generate a digest of all recent comments in a project created by a specific user. This makes it challenging to see what changed and what requires your action if you are collaborating with someone on a project.

This is a simple project which generates a digest of all comments by a particular user on a particular project.

This project was also a good excuse to play around and test some functional programming/data manipulation tooling I've been messing with ([funcy](https://github.com/Suor/funcy), [funcy-pipe](https://github.com/iloveitaly/funcy-pipe), and [whatever](https://github.com/Suor/whatever)).

## Features

* Can send an email digest if auth is provided
* Retrieves comments on completed tasks
* Target projects by ID or name

## Usage

### Docker

```shell
docker pull ghcr.io/iloveitaly/todoist-digest:latest
docker run --env-file .env ghcr.io/iloveitaly/todoist-digest:latest
```

Want to run a one off execution?

```shell
docker run --env-file .env ghcr.io/iloveitaly/todoist-digest:latest todoist-digest --help
```

Want to inspect the docker container?

```shell
docker run -it ghcr.io/iloveitaly/todoist-digest:latest bash
```

Or, just use the [docker compose file](docker-compose.yml).

### Locally


Run this locally using:

```shell
bin/local-digest-html
```

If you need a tty, you can copy the `todoist-digest` execution line and run it manually in a shell.

Or run directly:

```shell
poetry run todoist-digest \
  --last-synced "2023-12-04T15:52:48Z" \
  --target-user user@gmail.com \
  --target-project ProjectName
```

Or, email yourself the digest:

```shell
poetry run todoist-digest \
  --last-synced $LAST_SYNC \
  --target-user $TARGET_USER \
  --target-project $TARGET_PROJECT \
  --email-auth $EMAIL_AUTH \
  --email-to $EMAIL_TO
```

## Development

### Manual API Calls

```
http --auth-type bearer --auth $TODOIST_API_KEY https://api.todoist.com/rest/v2/projects 'Content-Type: application/json'
```

### Docker Build

This repo uses [nixpacks](https://nixpacks.com/docs/getting-started) for building a Dockerfile. Why? Because I like trying new things.

[Asdf support](https://github.com/railwayapp/nixpacks/pull/1026) is built into nixpacks, so it will automatically pick up python and poetry versions.

### Playground

ipython shell with some helpful variables defined:

```shell
./playground.py
```

### Run with ipdb

Open up an exception when there's an exception:

```shell
ipdb3 $(which todoist-digest) --last-synced 2023-12-14T13:38:25Z ...
```

## Related

* https://www.smashlists.com ([discovered here](https://www.reddit.com/r/todoist/comments/l7mhfq/how_to_track_weekly_goals/))