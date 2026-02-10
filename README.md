# Slurm Python Wrapper

(Docs made with love, by robots. Some info may not be 100% accurate)
A Python wrapper for submitting and managing Slurm jobs programmatically. This library provides an intuitive interface for creating Slurm batch scripts, submitting jobs, and monitoring their execution.

## Features

- **Simple job configuration** using Python objects or YAML files
- **Array job support** with automatic index management
- **Job monitoring** with status checks and completion blocking
- **Automatic script generation** from Python commands
- **Type hints** for better IDE support
- **Flexible time formatting** supporting `datetime.timedelta`

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/slurm-wrapper.git
cd slurm-wrapper

# No additional dependencies required beyond standard library
# Optional: Install PyYAML if using YAML configurations
pip install pyyaml
```

## Quick Start

### Basic Job Submission

```python
from supa_slurm import Slurm
import datetime

# Create a Slurm job manager
slurm = Slurm()

# Configure the job
slurm.add_arguments(
    job_name='my_job',
    partition='cpu',
    time=datetime.timedelta(hours=2),
    mem='8G',
    cpus_per_task=4
)

# Add commands to execute
slurm.add_commands(
    'module load python/3.9',
    'python my_script.py'
)

# Submit the job
jobs = slurm.sbatch()
print(f"Submitted job {jobs[0].job_id}")
```

### Array Job Submission

```python
from supa_slurm import Slurm

slurm = Slurm()

slurm.add_arguments(
    job_name='array_job',
    partition='gpu',
    time=datetime.timedelta(minutes=30),
    mem='4G',
    array=10  # Creates array indices 0-10
)

slurm.add_commands(
    'echo "Processing task $SLURM_ARRAY_TASK_ID"',
    'python process.py --task $SLURM_ARRAY_TASK_ID'
)

jobs = slurm.sbatch()
print(f"Submitted {len(jobs)} array tasks")
```

### Monitoring Job Status

```python
# Submit a job
jobs = slurm.sbatch()
job = jobs[0]

# Check status
status = job.get_status()
print(f"Job status: {status}")

# Wait for completion
job.hold_for_completion()
print("Job completed!")

# Cancel if needed
job.cancel()
```

## Configuration

### Using YAML Configuration

Create a default configuration file:

```yaml
# configs/slurm_default.yaml
partition: cpu
time: 01:00:00
mem: 4G
cpus_per_task: 1
output: slurm-%j.out
error: slurm-%j.err
```

Load and use:

```python
from supa_slurm import Slurm, SlurmConfig
from pathlib import Path

config = SlurmConfig.from_yaml('configs/slurm_default.yaml')
slurm = Slurm(config=config)
```

### Programmatic Configuration

```python
from supa_slurm import SlurmConfig, Slurm

# Create config directly
config = SlurmConfig(
    job_name='my_job',
    partition='gpu',
    gres='gpu:1',
    mem='16G'
)

slurm = Slurm(config=config)
```

## Advanced Usage

### Time Formatting

The wrapper accepts multiple time formats:

```python
import datetime

# Using timedelta (recommended)
slurm.add_arguments(time=datetime.timedelta(days=2, hours=4, minutes=30))
# Generates: 2-04:30:00

# Using string (Slurm format)
slurm.add_arguments(time='01:30:00')
```

### Array Job Specifications

```python
# Integer: creates array 0-N
slurm.add_arguments(array=5)  # Creates 0-5

# String range
slurm.add_arguments(array='1-10')  # Creates 1-10

# Python range
slurm.add_arguments(array=range(0, 100, 10))  # Creates 0-90 (step 10)
```

### Saving Job Configurations

```python
from pathlib import Path

# Specify output directory for scripts and configs
output_dir = Path('./job_outputs')
jobs = slurm.sbatch(
    output_path=output_dir,
    save_configuration=True  # Saves pickled config
)
```

### Working with Individual Array Tasks

```python
slurm.add_arguments(array=5)
jobs = slurm.sbatch()

# Each job represents one array task
for job in jobs:
    print(f"Job {job.job_id}, Array index {job.array_num}")
    print(f"Full array job ID: {job.array_job_id}")
```

## API Reference

### Slurm Class

Main interface for job management.

**Methods:**

- `add_arguments(**kwargs)`: Add SBATCH arguments
- `add_commands(*args)`: Add shell commands to execute
- `get_arguments()`: Retrieve current SBATCH arguments
- `sbatch(shell=None, save_configuration=True, output_path=None)`: Submit job
- `is_array_job()`: Check if configured as array job

### SlurmJob Class

Represents a submitted job (returned by `sbatch()`).

**Methods:**

- `get_status()`: Query current job status
- `is_queued()`: Check if job is pending or running
- `hold_for_completion(interval=3)`: Block until job completes
- `cancel()`: Cancel the job

**Attributes:**

- `job_id`: Slurm job ID
- `array_num`: Array index (for array jobs)
- `array_job_id`: Full array job identifier
- `submission_details`: Dict of job metadata from scontrol

### SlurmConfig Class

Internal configuration representation (usually not directly instantiated).

**Methods:**

- `from_yaml(path)`: Load configuration from YAML
- `add_command(cmd)`: Add a shell command
- `is_array_job()`: Check for array configuration

## Common SBATCH Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `job_name` | str | Name for the job | `'my_job'` |
| `partition` | str | Slurm partition | `'gpu'` |
| `time` | str/timedelta | Wall time limit | `datetime.timedelta(hours=2)` |
| `mem` | str | Memory per node | `'16G'` |
| `cpus_per_task` | int | CPUs per task | `4` |
| `gres` | str | Generic resources | `'gpu:2'` |
| `array` | int/str/range | Array job specification | `10` or `'0-9'` |
| `output` | str | stdout file path | `'logs/%j.out'` |
| `error` | str | stderr file path | `'logs/%j.err'` |
| `nodes` | int | Number of nodes | `1` |
| `ntasks` | int | Number of tasks | `1` |

## Examples

### GPU Job with Environment Setup

```python
from supa_slurm import Slurm
import datetime

slurm = Slurm()

slurm.add_arguments(
    job_name='gpu_training',
    partition='gpu',
    gres='gpu:v100:2',
    time=datetime.timedelta(hours=12),
    mem='32G',
    cpus_per_task=8
)

slurm.add_commands(
    'module load cuda/11.8',
    'module load python/3.10',
    'source venv/bin/activate',
    'python train.py --config config.yaml'
)

jobs = slurm.sbatch(output_path='./job_scripts')
```

### Parallel Data Processing

```python
from supa_slurm import Slurm
from pathlib import Path

slurm = Slurm()

slurm.add_arguments(
    job_name='process_data',
    partition='cpu',
    time=datetime.timedelta(minutes=30),
    mem='4G',
    array=100  # Process 100 files in parallel
)

slurm.add_commands(
    'python process_file.py --index $SLURM_ARRAY_TASK_ID'
)

jobs = slurm.sbatch()

# Wait for all tasks to complete
for job in jobs:
    job.hold_for_completion()

print("All processing complete!")
```

### Job Dependency Chain

```python
from supa_slurm import Slurm

# Job 1: Data preprocessing
preprocess = Slurm()
preprocess.add_arguments(job_name='preprocess', partition='cpu')
preprocess.add_commands('python preprocess.py')
job1 = preprocess.sbatch()[0]

# Job 2: Training (depends on job1)
train = Slurm()
train.add_arguments(
    job_name='train',
    partition='gpu',
    dependency=f'afterok:{job1.job_id}'
)
train.add_commands('python train.py')
job2 = train.sbatch()[0]
```

## Requirements

- Python 3.6+
- Access to a Slurm cluster
- PyYAML (optional, for YAML configuration support)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your license here]

## Troubleshooting

**Job submission fails:**
- Verify you're on a cluster with Slurm installed
- Check that `sbatch`, `squeue`, and `scancel` are in your PATH
- Verify partition names and resource limits

**Array jobs not working:**
- Ensure your cluster supports array jobs
- Check array size limits with your cluster admin

**Status checks return "COMPLETED or NOT FOUND":**
- This is normal for completed jobs (they leave the queue)
- Use Slurm accounting tools (e.g., `sacct`) for historical job data

## Acknowledgments

Built to simplify Slurm job management for Python-based HPC workflows.
