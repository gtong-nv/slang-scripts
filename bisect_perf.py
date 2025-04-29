import subprocess
import re
import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from colorama import init, Fore, Style

# Initialize colorama for Windows support
init()

# Path configurations
SLANG_REPO_PATH = r"C:\nv\slang"
SGL_REPO_PATH   = r"C:\nv\sgl"
PERF_TEST_PATH  = r"C:\nv\slangpy\examples\simplified-splatting"
BUILD_CMD       = "cmake --build build --config Release -j12"
GIT_SUBMODULE_UPDATE_CMD = "git submodule update --init --recursive"

# Create logs directory if it doesn't exist
log_dir = Path("bisect_logs")
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f'git_bisect_main_{timestamp}.log'),
        logging.StreamHandler()
    ]
)


def run_command(cmd, cwd=None, shell=True, phase=None, commit=None):
    """Run a command and return its output, saving logs regardless of success/failure"""
    print(f"Running command: {cmd}")
    try:
        # Create log file path
        log_file = log_dir / f'{commit}_{phase}_{timestamp}.log' if phase and commit else log_dir / f'command_{timestamp}.log'
        
        # Store complete output for return value
        complete_output = []
        
        with open(log_file, 'w', encoding='utf-8') as f:
            # Write header information to log file
            if phase and commit:
                f.write(f"Phase: {phase}\n")
                f.write(f"Commit: {commit}\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write("-" * 80 + "\n")
                f.write("OUTPUT:\n")
                f.flush()
            
            # Run process with pipe for output
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                bufsize=1,
                universal_newlines=True
            )
            
            # Read and handle output in real-time
            for line in process.stdout:
                # Store for return value
                complete_output.append(line)
                
                # Write to terminal
                sys.stdout.write(line)
                
                # Write to log file
                f.write(line)
                f.flush()
            
            # Wait for process to complete
            process.wait()
            
            # Check return code
            if process.returncode != 0:
                error_msg = f"Command returned non-zero exit code: {process.returncode}"
                logging.warning(error_msg)
                f.write(f"\nERROR: {error_msg}\n")
                raise subprocess.CalledProcessError(process.returncode, cmd, ''.join(complete_output))
            
            # Print completion message
            completion_msg = f"Command completed successfully with return code: {process.returncode}"
            print(f"{Fore.GREEN}{completion_msg}{Style.RESET_ALL}")
            f.write(f"\n{completion_msg}\n")
            
        return ''.join(complete_output)
        
    except subprocess.CalledProcessError as e:
        if phase and commit:
            logging.error(f"Command failed: {cmd}. Logs saved to {log_file}")
        raise

def checkout_commit(commit_hash, repo_path):
    """Checkout a specific commit"""
    logging.info(f"Checking out commit: {commit_hash}")
    try:
        run_command(f"git checkout {commit_hash}", cwd=repo_path, shell=True,
                   phase="checkout", commit=commit_hash)
        run_command(GIT_SUBMODULE_UPDATE_CMD, cwd=repo_path, shell=True,
                   phase="git_submodule_update", commit=commit_hash)
        return True
    except subprocess.CalledProcessError:
        logging.error(f"Failed to checkout commit {commit_hash}")
        return False

def build_slang(commit_hash):
    """Build the Slang project"""
    logging.info("Building Slang...")
    try:
        # Create a timestamped log file name for this build
        build_log_file = log_dir / f'slang_build_{commit_hash}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

        run_command(BUILD_CMD, 
                   cwd=SLANG_REPO_PATH,
                   phase="build_slang", 
                   commit=commit_hash)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Slang build: {e}")
        return True

def build_sgl(commit_hash):
    """Build the SGL project"""
    logging.info("Building SGL...")
    try:
        # Create a timestamped log file name for this build
        build_log_file = log_dir / f'sgl_build_{commit_hash}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        # Build command with verbose logging - using PowerShell redirection
        build_cmd = (
            f"cmake --build .\\build\\windows-vs2022 --config Release -j10 "
        )
        
        run_command(build_cmd, 
                   cwd=SGL_REPO_PATH,
                   phase="build_sgl", 
                   commit=commit_hash)
        return True
    except subprocess.CalledProcessError:
        logging.error("SGL build failed")
        return False

def run_perf_test(commit_hash):
    """Run the performance test and return the renderBlobsToTexture time"""
    logging.info("Running performance test...")
    try:
        output = run_command(
            "python3 .\\main.py",
            cwd=PERF_TEST_PATH,
            phase="perf_test", commit=commit_hash
        )
        
        # Parse the output to find renderBlobsToTexture time
        for line in output.split('\n'):
            if "renderBlobsToTexture" in line:
                match = re.search(r'renderBlobsToTexture: (\d+\.\d+)s', line)
                if match:
                    return float(match.group(1))
        
        logging.error("Could not find renderBlobsToTexture timing in output")
        return None
    except subprocess.CalledProcessError:
        logging.error("Performance test failed")
        return None

def evaluate_commit(commit_hash):
    """Evaluate a specific commit and return True if it's good (render time < 1s)"""
    results = {
        'commit': commit_hash,
        'checkout_success': False,
        'slang_build_success': False,
        'sgl_build_success': False,
        'perf_test_success': False,
        'render_time': None
    }
    
    try:
        # Checkout
        results['checkout_success'] = checkout_commit(commit_hash, SLANG_REPO_PATH)
        if not results['checkout_success']:
            logging.warning(f"Skipping commit {commit_hash} due to checkout failure")
            return None, results
        
        # Build Slang
        results['slang_build_success'] = build_slang(commit_hash)
        if not results['slang_build_success']:
            logging.warning(f"Skipping commit {commit_hash} due to Slang build failure")
            return None, results
        
        # Build SGL
        results['sgl_build_success'] = build_sgl(commit_hash)
        if not results['sgl_build_success']:
            logging.warning(f"Skipping commit {commit_hash} due to SGL build failure")
            return None, results
        
        # Run perf test
        render_time = run_perf_test(commit_hash)
        results['perf_test_success'] = render_time is not None
        results['render_time'] = render_time
        
        if render_time is None:
            logging.warning(f"Skipping commit {commit_hash} due to performance test failure")
            return None, results
        
        logging.info(f"Commit {commit_hash}: renderBlobsToTexture time = {render_time}s")
        return render_time < 1.0, results
        
    except Exception as e:
        logging.error(f"Unexpected error evaluating commit {commit_hash}: {str(e)}")
        return None, results

def main():
    if len(sys.argv) != 3:
        print("Usage: python bisect_perf.py <good_commit> <bad_commit>")
        sys.exit(1)

    good_commit = sys.argv[1]
    bad_commit = sys.argv[2]

    logging.info(f"Starting bisect between good commit {good_commit} and bad commit {bad_commit}")

    # Verify the commits exist and get their full hashes
    try:
        good_hash = run_command(f"git rev-parse {good_commit}", cwd=SLANG_REPO_PATH).strip()
        bad_hash = run_command(f"git rev-parse {bad_commit}", cwd=SLANG_REPO_PATH).strip()
    except subprocess.CalledProcessError:
        logging.error("Invalid commit hashes provided")
        sys.exit(1)

    # Start bisect
    run_command("git bisect start", cwd=SLANG_REPO_PATH)
    run_command(f"git bisect good {good_hash}", cwd=SLANG_REPO_PATH)
    run_command(f"git bisect bad {bad_hash}", cwd=SLANG_REPO_PATH)

    results = []
    try:
        while True:
            # Get current commit
            current_commit = run_command("git rev-parse HEAD", cwd=SLANG_REPO_PATH).strip()
            
            # Evaluate current commit
            is_good, eval_results = evaluate_commit(current_commit)
            results.append(eval_results)
            
            if is_good is None:
                logging.warning(f"Skipping commit {current_commit} due to evaluation failure")
                run_command("git bisect skip", cwd=SLANG_REPO_PATH)
                continue

            # Run git bisect good/bad based on result
            if is_good:
                output = run_command("git bisect good", cwd=SLANG_REPO_PATH)
            else:
                output = run_command("git bisect bad", cwd=SLANG_REPO_PATH)

            # Check if bisect is complete
            if "is the first bad commit" in output:
                logging.info("Bisect complete!")
                break

    except Exception as e:
        logging.error(f"Error during bisect: {str(e)}")
    finally:
        # End bisect
        run_command("git bisect reset", cwd=SLANG_REPO_PATH)

        # Write summary
        logging.info("\nBisect Summary:")
        for result in results:
            logging.info(f"\nCommit: {result['commit']}")
            logging.info(f"Checkout: {'✓' if result['checkout_success'] else '✗'}")
            logging.info(f"Slang Build: {'✓' if result['slang_build_success'] else '✗'}")
            logging.info(f"SGL Build: {'✓' if result['sgl_build_success'] else '✗'}")
            logging.info(f"Perf Test: {'✓' if result['perf_test_success'] else '✗'}")
            if result['render_time'] is not None:
                logging.info(f"Render time: {result['render_time']}s")
                logging.info(f"Status: {'good' if result['render_time'] < 1.0 else 'bad'}")

        # Save final summary to a separate file
        summary_file = log_dir / f'bisect_summary_{timestamp}.log'
        with open(summary_file, 'w') as f:
            f.write(f"Bisect between {good_hash} and {bad_hash}\n\n")
            for result in results:
                f.write(f"\nCommit: {result['commit']}\n")
                f.write(f"Checkout: {'✓' if result['checkout_success'] else '✗'}\n")
                f.write(f"Slang Build: {'✓' if result['slang_build_success'] else '✗'}\n")
                f.write(f"SGL Build: {'✓' if result['sgl_build_success'] else '✗'}\n")
                f.write(f"Perf Test: {'✓' if result['perf_test_success'] else '✗'}\n")
                if result['render_time'] is not None:
                    f.write(f"Render time: {result['render_time']}s\n")
                    f.write(f"Status: {'good' if result['render_time'] < 1.0 else 'bad'}\n")

if __name__ == "__main__":
    main()