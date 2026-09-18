#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pickle
import subprocess
from pathlib import Path


CHANNELS = {
    "v9-rheotool": ("v9", "foundation+rheotool"),
    "v10-foundation": ("v10", "foundation"),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh command-help text without recomputing command-name vectors"
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--channel", choices=CHANNELS, required=True)
    parser.add_argument(
        "--runner", type=Path,
        default=Path("/home/openfoam/Foam-Agent/scripts/run_openfoam_channel.sh"),
    )
    args = parser.parse_args()

    with args.index.open("rb") as stream:
        docstore, mapping = pickle.load(stream)

    version, distribution = CHANNELS[args.channel]
    for document in docstore._dict.values():
        command = document.metadata["command"]
        result = subprocess.run(
            [str(args.runner), args.channel, command, "-help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        help_text = result.stdout.strip()
        if not help_text:
            raise RuntimeError(f"No help output for command: {command}")
        document.metadata.update({
            "help_text": help_text,
            "full_content": f"<command>{command}</command><help_text>\n{help_text}\n</help_text>",
            "channel": args.channel,
            "version": version,
            "distribution": distribution,
        })

    with args.index.open("wb") as stream:
        pickle.dump((docstore, mapping), stream)
    print(f"Refreshed {len(docstore._dict)} commands for {args.channel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
