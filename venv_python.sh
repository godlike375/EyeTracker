#!/usr/bin/env bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

REPO_DIR="$SCRIPT_DIR/."

if [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" ]]; then
	./venv_python.cmd "$@"
	exit $?
fi

source "REPO_DIR/venv/bin/activate"

python "$@"
