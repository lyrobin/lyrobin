"""Function to create a batch job on Google Cloud Platform."""

import firebase_admin  # type: ignore
from google.cloud import batch_v1

DEFAULT_REGION = "asia-east1"


def create_container_job(
    image_uri: str,
    job_name: str = "",
    env_vars: dict[str, str] | None = None,
    secret_env_vars: dict[str, str] | None = None,
    project_id: str = "",
    region: str = "",
) -> batch_v1.Job:
    """
    This method shows how to create a sample Batch Job that will run
    a simple command inside a container on Cloud Compute instances.

    Args:
        project_id: project ID or project number of the Cloud project you want to use.
        region: name of the region you want to use to run the job. Regions that are
            available for Batch are listed on: https://cloud.google.com/batch/docs/get-started#locations
        job_name: the name of the job that will be created.
            It needs to be unique for each project and region pair.

    Returns:
        A job object representing the job created.
    """
    if env_vars is None:
        env_vars = {}
    if secret_env_vars is None:
        secret_env_vars = {}
    if not project_id:
        app: firebase_admin.App = firebase_admin.get_app()
        project_id = app.project_id
    region = region or DEFAULT_REGION

    client = batch_v1.BatchServiceClient()

    # Define what will be done as part of the job.
    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = image_uri

    # Jobs can be divided into tasks. In this case, we have only one task.
    task = batch_v1.TaskSpec()
    task.runnables = [runnable]
    task.environment.variables.update(env_vars)  # pylint: disable=no-member
    task.environment.secret_variables.update(  # pylint: disable=no-member
        secret_env_vars
    )

    # We can specify what resources are requested by each task.
    resources = batch_v1.ComputeResource()
    resources.cpu_milli = 2000  # in milliseconds per cpu-second. This means the task requires 2 whole CPUs.
    resources.memory_mib = 1024 * 2  # in MiB, 2 GiB of memory.
    task.compute_resource = resources

    task.max_retry_count = 2
    task.max_run_duration = "3600s"  # 1 hour

    # Tasks are grouped inside a job using TaskGroups.
    # Currently, it's possible to have only one task group.
    group = batch_v1.TaskGroup()
    group.task_count = 1
    group.task_spec = task

    # Policies are used to define on what kind of virtual machines the tasks will run on.
    # In this case, we tell the system to use "e2-standard-4" machine type.
    # Read more about machine types here: https://cloud.google.com/compute/docs/machine-types
    policy = batch_v1.AllocationPolicy.InstancePolicy()
    policy.machine_type = "e2-standard-2"
    instances = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instances.policy = policy
    allocation_policy = batch_v1.AllocationPolicy()
    allocation_policy.instances = [instances]

    job = batch_v1.Job()
    job.task_groups = [group]
    job.allocation_policy = allocation_policy
    job.labels = {"env": "testing", "type": "container"}
    # We use Cloud Logging as it's an out of the box available option
    job.logs_policy = batch_v1.LogsPolicy()
    job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING  # type: ignore

    create_request = batch_v1.CreateJobRequest()
    create_request.job = job
    create_request.job_id = job_name
    # The job's parent is the region in which the job will run
    create_request.parent = f"projects/{project_id}/locations/{region}"

    return client.create_job(create_request)
