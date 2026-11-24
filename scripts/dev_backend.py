import os
import socket

import uvicorn
from watchfiles import PythonFilter, run_process


def main():
    host = '127.0.0.1'
    port = int(os.environ.get('UVICORN_PORT', '8000'))
    try:
        with socket.socket() as probe:
            probe.bind((host, port))
    except OSError as error:
        raise SystemExit(f'Could not bind to {host}:{port}: {error}') from error

    # Run the server in a child process so reload does not depend on Windows console signals.
    run_process(
        'backend',
        target=uvicorn.run,
        args=('backend.app:app',),
        kwargs={'host': host, 'port': port},
        watch_filter=PythonFilter(),
    )


if __name__ == '__main__':
    main()
