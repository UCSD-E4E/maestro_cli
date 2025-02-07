from kubernetes import client, config, utils
import yaml
import importlib.resources as pkg_resources
import click

from maestro_cli.util import load_cfg
from maestro_cli import job_configs

try:
  config.load_kube_config()
except Exception as e:
  click.echo("NO CONFIG FOUND")
  click.ClickException(e)

v1 = client.ApiClient()
batch_v1_api = client.BatchV1Api()
core_v1_api = client.CoreV1Api()
networking_v1_api = client.NetworkingV1Api()

## FUNCTION BY CHATGPT
def load_yaml(filename):
    with pkg_resources.files(job_configs).joinpath(filename).open("r") as f:
        return yaml.safe_load(f)

def spin_up_jobs(cfg):
    uuid = cfg["UUID"]
    k8sapp = f"{uuid}-maestro-svc"
    ingress_name = f"{uuid}-maestro-ingress"
    url = cfg["ingress_url"]
    scheduler_name = f"{uuid}-maestro-scheduler"
    namespace = cfg["namespace"]
    pvc_name = f"{uuid}-maestro-data-pvc"

    net = load_yaml("run_schuduler-net.yaml")
    net["metadata"]["name"] = k8sapp
    net["metadata"]["labels"]["k8s-app"] = k8sapp
    net["metadata"]["labels"]["group"] = uuid
    net["spec"]["selector"]["k8s-app"] = k8sapp
   
    ingress = load_yaml("run_schuduler-ingress.yaml")
    ingress["metadata"]["name"] = ingress_name
    ingress["metadata"]["labels"]["group"] = uuid
    ingress["spec"]["rules"][0]["host"] = url
    ingress["spec"]["tls"][0]["hosts"] = [url]
    ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]["name"] = k8sapp
    
    scheduler = load_yaml("run_schuduler.yaml")
    scheduler["metadata"]["name"] = scheduler_name
    scheduler["metadata"]["labels"]["group"] = uuid
    scheduler["spec"]["template"]["metadata"]["labels"]["k8s-app"] = scheduler_name
    scheduler["spec"]["template"]["metadata"]["name"] = scheduler_name

    scheduler["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]["name"] = pvc_name
    scheduler["spec"]["template"]["spec"]["volumes"][0]["name"] = pvc_name
    scheduler["spec"]["template"]["spec"]["volumes"][0]["persistentVolumeClaim"]["claimName"] = pvc_name
    ## TODO add config for scheduler container name and where to pull it...

    pvc = load_yaml("run_storage.yaml")
    pvc["metadata"]["name"] = pvc_name
    pvc["metadata"]["labels"]["group"] = uuid

    ## Spin jobs up actually
    try:
        utils.create_from_dict(v1, pvc, verbose=True, namespace=namespace)
    except Exception as e:
        print("pvc already exists likely")
    utils.create_from_dict(v1, net, verbose=True, namespace=namespace)
    utils.create_from_dict(v1, ingress, verbose=True, namespace=namespace)
    utils.create_from_dict(v1, scheduler, verbose=True, namespace=namespace)


def delete_all_object(search_cmd, delete_cmd, namespace, label_selector, dry_run=False):
    ret = search_cmd(namespace, label_selector=label_selector)
    for i in ret.items:
        #print(i.metadata.name)
        if (not dry_run):
            delete_cmd(i.metadata.name, "krg-maestro")

def spin_down_jobs(cfg, keep_storage=True):
    uuid = cfg["UUID"]
    namespace = cfg["namespace"]
    label_selector = f"group={uuid}"
    
    delete_all_object(
        batch_v1_api.list_namespaced_job, 
        batch_v1_api.delete_namespaced_job,
        namespace, label_selector, dry_run=False
    )
    
    delete_all_object(
        core_v1_api.list_namespaced_pod, 
        core_v1_api.delete_namespaced_pod,
        namespace, label_selector, dry_run=False
    )

    delete_all_object(
        networking_v1_api.list_namespaced_ingress, 
        networking_v1_api.delete_namespaced_ingress, 
        namespace, label_selector, dry_run=False
    )

    delete_all_object(
        core_v1_api.list_namespaced_service, 
        core_v1_api.delete_namespaced_service,
        namespace, label_selector, dry_run=False
    )
    if (not keep_storage):
        delete_all_object(
            core_v1_api.list_namespaced_persistent_volume_claim, 
            core_v1_api.delete_namespaced_persistent_volume_claim, 
            namespace, label_selector, dry_run=False
        ) 

#https://stackoverflow.com/questions/66683268/how-can-i-list-all-pods-in-a-kubernetes-cluster-in-python
def process_object_list(ret):
    return_form = []
    for i in ret.items:
        print("%s" % (i.metadata.name))

def list_all_kube_objects(cfg):
    uuid = cfg["UUID"]
    namespace = cfg["namespace"]
    label_selector = f"group={uuid}"
    print(process_object_list(
        batch_v1_api.list_namespaced_job(namespace, label_selector=label_selector)
    ))
    print(process_object_list(
        core_v1_api.list_namespaced_pod(namespace, label_selector=label_selector)
    ))
    print(process_object_list(
        networking_v1_api.list_namespaced_ingress(namespace, label_selector=label_selector)
    ))
    print(process_object_list(
        core_v1_api.list_namespaced_service(namespace, label_selector=label_selector))
    )
    print(process_object_list(
        core_v1_api.list_namespaced_persistent_volume_claim(namespace, label_selector=label_selector))
    )