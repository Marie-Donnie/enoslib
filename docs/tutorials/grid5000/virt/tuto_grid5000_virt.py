from enoslib.api import generate_inventory, run_ansible
from enoslib.infra.enos_g5k.provider import G5k
import logging
from netaddr import EUI
import os

logging.basicConfig(level=logging.DEBUG)

VMS = 5
PMS = 2


def range_mac(mac_start, mac_end, step=1):
    """Iterate over mac addresses (given as string)."""
    start = int(EUI(mac_start))
    end = int(EUI(mac_end))
    for i_mac in range(start, end, step):
        mac = EUI(int(EUI(i_mac)) + 1)
        ip = ['10'] + [str(int(i, 2)) for i in mac.bits().split('-')[-3:]]
        yield str(mac).replace('-', ':'), '.'.join(ip)

provider_conf = {
    "job_type": "allow_classic_ssh",
    "job_name": "test-non-deploy",
    "walltime": "3:00:00",
    "resources": {
        "machines": [{
            "role": "compute",
            "cluster": "parapluie",
            "nodes": PMS,
            "primary_network": "n1",
            "secondary_networks": []
        }],
        "networks": [{
            "id": "n1",
            "type": "prod",
            "role": "my_network",
            "site": "rennes",
         }, {
            "id": "not_linked_to_any_machine",
            "type": "slash_22",
            "role": "my_subnet",
            "site": "rennes",
         }]
    }
}

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
provider = G5k(provider_conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
generate_inventory(roles, networks, inventory, check_networks=True)

subnet = [n for n in networks if "my_subnet" in n["roles"]][0]
mac_start = subnet["mac_start"]
mac_end = subnet["mac_end"]

vms = []

# Distribute mac addresses to vms
for idx, (mac, ip) in enumerate(range_mac(mac_start, mac_end)):
    if len(vms) >= VMS:
       break
    name = "vm-%s" % idx
    vms.append({
        "name": name,
        "cores": 2,
        "mem": 2048000,
        "mac": mac,
        "backing_file": "/tmp/%s.qcow2" % name,
        "ip": ip

    })

# Distribute vms to pms
machines = roles["compute"]
for index, vm in enumerate(vms):
    # host is set to the inventory hostname
    vm["host"] = machines[index % len(machines)].alias

logging.info(vms)

run_ansible(["site.yml"], inventory, extra_vars={"vms": vms})

print("If everything went fine you can access one of those")
print("+{:->16}+{:->16}+".format('', ''))
for idx, vm in enumerate(vms):
    print('|{:16}|{:16}|'.format(vm["name"], vm["ip"]))
    print("+{:->16}+{:->16}+".format('', ''))


# destroy the reservation
# provider.destroy()