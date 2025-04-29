# Performance Regression Bisect Tool

This tool automates the process of finding performance regressions in the Slang codebase using Git bisect. It specifically tracks the `renderBlobsToTexture` in the `https://github.com/shader-slang/slangpy/blob/main/examples/simplified-splatting/main.py#L90` performance metric and identifies when it crossed a 1-second threshold.
It's easy to adapt to use another metric for another test.

## Prerequisites

- Python 3.x
- Git
- CMake
- Colorama (`pip install colorama`)

## Configuration

The script uses the following paths (configured at the top of `bisect_perf.py`):

```python
SLANG_REPO_PATH = r"C:\nv\slang"
SGL_REPO_PATH   = r"C:\nv\sgl"
PERF_TEST_PATH  = r"C:\nv\slangpy\examples\simplified-splatting"
```

## Usage

```bash
python bisect_perf.py <good_commit> <bad_commit>
```

Where:
- `good_commit`: The last known good commit (render time < 1s)
- `bad_commit`: A commit where the performance regression is present (render time > 1s)

## How It Works

### Main Workflow

1. **Setup Phase**
   - Validates input commit hashes
   - Initializes git bisect
   - Creates log directory for output

2. **Bisect Loop**
   - For each commit being tested:
     - Checks out the commit
     - Updates git submodules
     - Builds Slang
     - Builds SGL
     - Runs performance test
     - Determines if commit is "good" or "bad"
     - Continues until the first bad commit is found

3. **Results**
   - Generates detailed logs for each step
   - Creates a final summary report

### Evaluation Process

For each commit, the script:

1. **Checkout & Setup**
   ```python
   results['checkout_success'] = checkout_commit(commit_hash, SLANG_REPO_PATH)
   ```

2. **Build Process**
   ```python
   results['slang_build_success'] = build_slang(commit_hash)
   results['sgl_build_success'] = build_sgl(commit_hash)
   ```

3. **Performance Testing**
   ```python
   render_time = run_perf_test(commit_hash)
   is_good = render_time < 1.0
   ```

### Sample Output

```
2024-03-18 14:30:22 - INFO - Starting bisect between good commit abc123 and bad commit def456

2024-03-18 14:30:23 - INFO - Checking out commit: abc123
Running command: git checkout abc123
Running command: git submodule update --init --recursive
Command completed successfully with return code: 0

2024-03-18 14:30:25 - INFO - Building Slang...
Running command: cmake --build build --config Release -j12
[... build output ...]
Command completed successfully with return code: 0

2024-03-18 14:35:30 - INFO - Commit abc123: renderBlobsToTexture time = 0.85s

[... bisect continues ...]

Bisect Summary:
Commit: abc123
Checkout: ✓
Slang Build: ✓
SGL Build: ✓
Perf Test: ✓
Render time: 0.85s
Status: good

Commit: def456
Checkout: ✓
Slang Build: ✓
SGL Build: ✓
Perf Test: ✓
Render time: 1.25s
Status: bad
```

## Log Files

The script generates several types of log files in the `bisect_logs` directory:

1. **Main Log**: `git_bisect_main_TIMESTAMP.log`
   - Overall bisect process log
   - Contains high-level information and errors

2. **Command Logs**: `COMMIT_PHASE_TIMESTAMP.log`
   - Detailed output for each command
   - Includes build output, test results, etc.

3. **Summary File**: `bisect_summary_TIMESTAMP.log`
   - Final report of all tested commits
   - Shows success/failure of each step
   - Includes render times and good/bad status
