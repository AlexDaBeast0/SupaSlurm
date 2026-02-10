from typing import Optional, List, Dict, Union
from pathlib import Path

import yaml
import pickle
import tempfile
import datetime
import subprocess
import re
import time


class SlurmConfig:
    '''
    Internal representation of a Slurm job configuration.

    This class is responsible for storing SBATCH arguments, shell settings,
    and the list of commands that will be executed by the job. It is primarily
    used internally by the `Slurm` class and is not intended to be interacted
    with directly by most users.

    The configuration can be rendered as a valid Slurm submission script
    via its string representation.
    '''

    def __init__(self, shell: str = None, **kwargs):
        '''
        Initialize a SlurmConfig object.

        Parameters
        ----------
        shell : str, optional
            Shell used at the top of the submission script (default: /bin/bash).
        **kwargs
            Arbitrary SBATCH arguments (e.g. job_name, partition, time, mem).
            Keyword names should use underscores instead of hyphens and will be
            converted automatically.
        '''
        self._args = {}
        self._commands = []
        self.shell = shell or '/bin/bash'

        for key, val in kwargs.items():
            self._args[key] = val
            setattr(self, key, val)

    def __repr__(self) -> str:
        return f'SlurmConfig(job_name={self.job_name or None}, partition={self.partition or None}, time={self.time or None})'
    
    def __str__(self) -> str:
        s = f'#!{self.shell}'
        for arg, val in self._args.items():
            arg = arg.replace('_', '-')
            s += f'\n#SBATCH --{arg}={val}'
        for command in self._commands:
            s += f'\n{command}'
        return s
    
    def add_command(self, cmd : str):
        '''
        Add a shell command to be executed by the job.

        Parameters
        ----------
        cmd : str
            A shell command to run inside the Slurm job.
        '''
        self._commands.append(cmd)

    def is_array_job(self) -> bool:
        '''
        Determine whether this configuration represents a Slurm array job.

        Returns
        -------
        bool
            True if an array argument is present, False otherwise.
        '''
        return 'array' in self._args.keys()

    @classmethod
    def from_yaml(cls, path: str = Path(__file__).parent.resolve() / 'configs' / 'slurm_default.yaml') -> 'SlurmConfig':
        '''
        Create a SlurmConfig from a YAML file.

        The YAML file should contain key-value pairs corresponding to SBATCH
        arguments.

        Parameters
        ----------
        path : str or Path, optional
            Path to a YAML configuration file.

        Returns
        -------
        SlurmConfig
            A populated SlurmConfig instance.
        '''
        cls.job_name = ''
        path = str(path)
        
        with open(path, 'r') as y:
            yaml_data = yaml.safe_load(y) or {}
        return cls(**yaml_data)


class Slurm:
    '''
    High-level interface for creating, submitting, and managing Slurm jobs.

    This is the primary class users should interact with. It wraps a
    `SlurmConfig` object and provides methods to add SBATCH arguments,
    append commands, submit jobs, and access submitted job objects.
    '''

    def __init__(self, config : SlurmConfig = None):
        '''
        Initialize a Slurm job manager.

        Parameters
        ----------
        config : SlurmConfig, optional
            A preconfigured SlurmConfig. If None, defaults are loaded from YAML.
        '''
        self.config = config or SlurmConfig.from_yaml()

    def __str__(self) -> str:
        return self.config.__str__()
    
    def __repr__(self) -> str:
        return f'SlurmJob'

    # Editing defaults / interacting with
    def add_arguments(self, **kwargs) -> None:
        '''
        Add or update SBATCH arguments for the job.

        Special handling is provided for:
        - `time`: accepts datetime.timedelta and converts to Slurm format
        - `array`: accepts int, str (e.g. "0-4"), or range-like inputs

        Parameters
        ----------
        **kwargs
            SBATCH arguments such as partition, time, job_name, mem, array, etc.
        '''
        for key, val in kwargs.items():
            if key == 'time' and isinstance(val, datetime.timedelta):
                total_s = int(val.total_seconds())

                days, rem = divmod(total_s, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, seconds = divmod(rem, 60)

                val = f'{days}-{hours:02}:{minutes:02}:{seconds:02}'

            if key == 'array' and not isinstance(key, tuple):
                if isinstance(val, str):
                    val = val.split('-')
                    val = list(map(int, val))
                    val = range(val[0], val[-1]+1) # slurm arrays are left and right inclusive while python range is only left
                elif isinstance(val, int):
                    val = range(0, val+1) # assuming if just int then we include 0
                self.config._args[key] = f'{val[0]}-{val[-1]}'
                setattr(self.config, key, val)
                continue

            self.config._args[key] = val
            setattr(self.config, key, val)

    def add_commands(self, *args) -> None:
        '''
        Add one or more shell commands to the job.

        Parameters
        ----------
        *args : str
            Shell commands to execute in order.

        '''
        for cmd in args:
            self.config._commands.append(cmd)

    def get_arguments(self) -> Dict[str, str]:
        '''
        Retrieve the current SBATCH arguments.

        Returns
        -------
        dict
            Mapping of SBATCH argument names to values.
        '''
        return self.config._args
    
    def get_commands(self) -> List[str]:
        '''
        Retrieve the list of shell commands for the job.

        Returns
        -------
        list of str
            Commands that will be executed by the job.
        '''
        return self.config._args
    
    # Script submission
    def _write_submission_script(self, path: str, suffix: str = '.sh', save:bool=True) -> str:
        '''
        Write the Slurm submission script to disk.

        Parameters
        ----------
        path : str or Path
            Base path for the script file.
        suffix : str, optional
            File extension to use (default: .sh).
        save : bool, optional
            Whether to persist the script to disk.

        Returns
        -------
        str
            Path to the written submission script.
        '''
        path = Path(path) or Path(path).parent.resolve() / self.job_name
        path = str(path.with_suffix(suffix))

        with open(path, 'w') as f:
            f.write(self.config.__str__())
            return path
    
    def _serialize_config(self, path: str, suffix: str = '.pkl') -> None:
        '''
        Serialize the SlurmConfig object to disk using pickle.

        Parameters
        ----------
        path : str or Path
            Output path.
        suffix : str, optional
            File extension for the serialized configuration.
        '''
        path = Path(path) or Path(path).parent.resolve() / f'{self.job_name}'
        path = str(path.with_suffix(suffix))

        with open(path, 'wb') as p:
            pickle.dump(self.config, p)
            return path
        
    def is_array_job(self) -> bool:
        return self.config.is_array_job()
    
    def sbatch(self, shell: str = None, save_configuration: bool = True, output_path: str = None) -> List[Optional['SlurmJob']]:
        '''
        Submit the job to Slurm using `sbatch`.

        This method writes the submission script, optionally saves the job
        configuration, submits the job, and returns SlurmJob objects representing
        the submitted job(s).

        Parameters
        ----------
        shell : str, optional
            Override the shell used in the submission script.
        save_configuration : bool, optional
            Whether to pickle and save the SlurmConfig.
        output_path : str or Path, optional
            Directory where scripts and configs will be written.

        Returns
        -------
        list of SlurmJob
            One SlurmJob for a normal job, or multiple for array jobs.
        '''
        shell = shell or self.config.shell
        if output_path is None:
            output_path = Path(__file__).parent.resolve() 
        else:
            output_path = Path(output_path)
        output_path.mkdir(exist_ok=True)

        if save_configuration:
            configuration_path = self._serialize_config(path=output_path / f'{self.config.job_name}')
        submission_script_path = self._write_submission_script(path=output_path / f'{self.config.job_name}')

        # Sbatch submission
        process = subprocess.run(['sbatch', f'{submission_script_path}'], capture_output=True, text=True, check=True)
        match = re.search(r"Submitted batch job (\d+)", process.stdout)

        self.stdout = process.stdout
        self.stderr = process.stderr
        self.jobs = []

        if match:
            self.job_id = match.group(1)
            if self.config.is_array_job():
                self.jobs = [SlurmJob(f'{self.job_id}', self, array_num = i) for i in self.config.array]
            else:
                self.jobs = [SlurmJob(f'{self.job_id}', self)]
        return self.jobs
    

class SlurmJob:
    '''
    Representation of a submitted Slurm job or array task.

    Instances of this class are returned by `Slurm.sbatch` and provide
    utilities for querying job status, waiting for completion, and
    cancelling jobs.
    '''

    def __init__(self, job_id: str, slurm: Slurm, array_num:Union[int, str]):
        '''
        Initialize a SlurmJob instance.

        Parameters
        ----------
        job_id : str
            Slurm job ID assigned by the scheduler.
        slurm : Slurm
            Parent Slurm object that submitted the job.
        array_num : int or str
            Array index for array jobs.
        '''
        self.job_id = job_id
        self.slurm = slurm
        self.array_num = int(array_num)
        self.__dict__.update(slurm.__dict__)

        if self.slurm.is_array_job():
            self.array_job_id = f'{self.job_id}_{self.array_num}'
        
        self.submission_details = self._get_scontrol_attrs()
        # self.submission_config = SlurmConfig(**self.submission_details) # Class has capacity to hold this data but it treats it like a slurm submission
    
    def __str__(self) -> str:
        return self.job_id
    
    def __repr__(self) -> str:
        return f'SlurmJob(job_id={self.job_id})'
    
    def _get_scontrol_attrs(self) -> Dict[str, str]:
        '''
        Retrieve job submission details using `scontrol show job`.

        Returns
        -------
        dict
            Mapping of Slurm job attributes to values.
        '''
        process = subprocess.run(['scontrol', 'show', 'job', self.job_id],capture_output=True, text=True, check=True)
        submission_details = {}
        for attr in process.stdout.split(' '):
            attr = attr.strip()
            if attr:
                key, val = attr.split('=', 1)
                submission_details[key] = val
        return submission_details
        

    def get_status(self):
        '''
        Query the current job status using `squeue`.

        Returns
        -------
        str
            Slurm job state (e.g. PENDING, RUNNING) or
            'COMPLETED or NOT FOUND' if the job is no longer queued.
        '''
        try:
            process = subprocess.run(["squeue", "-j", self.job_id, "-h", "-o", "%T"],capture_output=True, text=True, check=True)
            if process.stdout:
                return process.stdout.strip()
            else:
                return 'COMPLETED or NOT FOUND'
        except subprocess.CalledProcessError:
            return 'COMPLETED or NOT FOUND'
        
    def hold_for_completion(self, interval:int = 3) -> None:
        '''
        Block execution until the job has completed.

        Parameters
        ----------
        interval : int, optional
            Time in seconds between status checks.
        '''
        while True:
            if self.is_queued():
                time.sleep(interval)
                continue
            break

    def is_queued(self) -> bool:
        '''
        Check whether the job is still pending or running.

        Returns
        -------
        bool
            True if job is queued or running, False otherwise.
        '''
        return self.get_status() in ('PENDING', 'RUNNING')
    
    def cancel(self) -> bool:
        '''
        Cancel the job using `scancel`.

        Returns
        -------
        bool
            True if cancellation was successful, False otherwise.
        '''
        if not self.is_queued:
            return False

        try:
            subprocess.run(["scancel", self.job_id], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False


if __name__ == '__main__':
    dir = Path(__file__).parent.resolve()

    slurm = Slurm(config=SlurmConfig.from_yaml(dir / 'configs' / 'slurm_default.yaml'))
    slurm.add_commands('sleep 10', 'echo HIII')
    slurm.add_arguments(partition='gpu',
                        time=datetime.timedelta(seconds=15),
                        job_name='test',
                        mem='4G',
                        array=3)
    
    slurm.sbatch(output_path=Path(__file__).parent.resolve() / 'outputs')
    
    if slurm.is_array_job():
        for job in slurm.jobs:
            job.hold_for_completion()
            