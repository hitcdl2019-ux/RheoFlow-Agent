import os
import subprocess
import sys
import argparse
import shlex

def parse_args():
    parser = argparse.ArgumentParser(description="Initialize database for Foam-Agent project")
    parser.add_argument(
        '--openfoam_path',
        type=str,
        default=os.getenv("WM_PROJECT_DIR"),
        help="Path to OpenFOAM installation (WM_PROJECT_DIR)"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force re-generate raw tutorial dumps + FAISS indices even if files exist"
    )
    parser.add_argument(
        '--extra_tutorial_path',
        action='append',
        default=[],
        help="Additional tutorial root to merge into the RAG corpus. Can be passed multiple times."
    )
    parser.add_argument(
        '--extra_command_bin',
        action='append',
        default=[],
        help="Additional bin directory whose command help should be indexed. Can be passed multiple times."
    )
    parser.add_argument(
        '--embedding_provider',
        type=str,
        default='huggingface',
        choices=['openai', 'huggingface', 'ollama'],
        help="Embedding provider used to rebuild FAISS indices"
    )
    parser.add_argument(
        '--embedding_model',
        type=str,
        default='Qwen/Qwen3-Embedding-0.6B',
        help="Embedding model used to rebuild FAISS indices"
    )
    return parser.parse_args()

def run_command(command_str):
    """
    Execute a command string using the current terminal's input/output,
    with the working directory set to the directory of the current file.
    
    Parameters:
        command_str (str): The command to execute, e.g. "python main.py --output_dir xxxx" 
                           or "bash xxxxx.sh".
    """
    # Split the command string into a list of arguments
    args = shlex.split(command_str)
    # Set the working directory to the directory of the current file
    cwd = os.path.dirname(os.path.abspath(__file__))
    
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
            stdin=sys.stdin
        )
        print(f"Finished command: Return Code {result.returncode}")
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(e.returncode)

def main():
    args = parse_args()
    print(args)

    # Set environment variables
    WM_PROJECT_DIR = args.openfoam_path
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"script_dir: {script_dir}")

    SCRIPTS = []
    
    # Preprocess the OpenFOAM tutorials
    extra_tutorial_args = " ".join(
        f"--extra_tutorial_path={shlex.quote(path)}" for path in args.extra_tutorial_path
    )
    extra_command_args = " ".join(
        f"--extra_command_bin={shlex.quote(path)}" for path in args.extra_command_bin
    )
    embedding_args = (
        f"--embedding_provider={shlex.quote(args.embedding_provider)} "
        f"--embedding_model={shlex.quote(args.embedding_model)}"
    )

    if args.force or not os.path.exists(f"{script_dir}/database/raw/openfoam_tutorials_details.txt"):
        SCRIPTS.append(
            f"python database/script/tutorial_parser.py --output_dir=./database/raw --wm_project_dir={shlex.quote(WM_PROJECT_DIR)} "
            f"{extra_tutorial_args} {extra_command_args}"
        )

    # (Re)build FAISS indices
    if args.force or not os.path.exists(f"{script_dir}/database/faiss/openfoam_command_help"):
        SCRIPTS.append(f"python database/script/faiss_command_help.py --database_path=./database {embedding_args}")
    if args.force or not os.path.exists(f"{script_dir}/database/faiss/openfoam_allrun_scripts"):
        SCRIPTS.append(f"python database/script/faiss_allrun_scripts.py --database_path=./database {embedding_args}")
    if args.force or not os.path.exists(f"{script_dir}/database/faiss/openfoam_tutorials_structure"):
        SCRIPTS.append(f"python database/script/faiss_tutorials_structure.py --database_path=./database {embedding_args}")
    if args.force or not os.path.exists(f"{script_dir}/database/faiss/openfoam_tutorials_details"):
        SCRIPTS.append(f"python database/script/faiss_tutorials_details.py --database_path=./database {embedding_args}")

    if not SCRIPTS:
        print("All database files already exist. No initialization needed.")
        print("Tip: pass --force to rebuild.")
        return

    print("Starting database initialization...")
    for script in SCRIPTS:
        run_command(script)
    print("Database initialization completed successfully.")

if __name__ == "__main__":
    ## python init_database.py --openfoam_path $WM_PROJECT_DIR
    main()

