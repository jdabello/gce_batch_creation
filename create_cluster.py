#get/parse arguments
import argparse
#validate ip
import re
#OAUTH
from oauth2client.client import GoogleCredentials
#Google cloud client library
from googleapiclient import discovery
from apiclient.http import BatchHttpRequest
#log
import json

def format_prefix_ip_address(argument):
	global ginitial_ip
	#TODO Fix regexp, also check that it has enough ip address for this deployment
	if not re.match(r"^(?:10|127|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\..*",argument):
		raise argparse.ArgumentTypeError("Invalid IP address")
	else:
		splitIp =  argument.split('.')
		prefixIp =  "%s.%s.%s." % (splitIp[0],splitIp[1],splitIp[2])
		ginitial_ip = int(splitIp[3])-1
		return prefixIp

def get_arguments():
	global gprojectid, gnumbernodes, gnodeprefix, gzone, gmachine_type, gimage_family, gimage_project,gnetwork,gno_address, gtags, gprefix_private_network_ip, ginitial_ip
	global gjsonoutput
	gjsonoutput={}
	parser = argparse.ArgumentParser(description="A wrapper of gcloud to create tons of vms in seconds!")
	parser.add_argument("projectid", help="Set the project id.")
	parser.add_argument("numbernodes", help="Set the number of nodes that you want to create.", type=int)
	parser.add_argument("--nodeprefix", help="Set the prefix for your nodes. [default=node]", default="node")
	parser.add_argument("--zone", help="Set the zone for your nodes. [default=us-central1-f]", default="us-central1-f")
	parser.add_argument("--machinetype", "--machine-type", help="Set the machine type for your nodes. [default=f1-micro]", default="f1-micro")
	parser.add_argument("--imagefamily", "--image-family", help="The family of the image that the boot disk will be initialized with. [default=centos-7]", default="centos-7")
	parser.add_argument("--imageproject", "--image-project", help="The project against which all image and image family references will be resolved. [default=centos-cloud]", default="centos-cloud")
	parser.add_argument("--network", help="Specifies the network that the instances will be part of. [default=default]", default="default")
	parser.add_argument("--noaddress", "--no-address", help="If provided, the instances will not be assigned external IP addresses.", action="store_true")
	parser.add_argument("--tags", help="pecifies a list of tags to apply to the instances for identifying the instances to which network firewall rules will apply. See gcloud compute firewall-rules create(1) for more details.")
	parser.add_argument("--prefixprivatenetworkip","--prefix-private-network-ip", help="Specifies the RFC1918 IP to assign to the instance. The IP should be in the subnet or legacy network IP range.", type=format_prefix_ip_address)
	

	args = parser.parse_args()
	gprojectid=args.projectid
	gnumbernodes=args.numbernodes
	gnodeprefix=args.nodeprefix
	gzone=args.zone
	gmachine_type=args.machinetype
	gimage_family=args.imagefamily
	gimage_project=args.imageproject
	gnetwork=args.network
	gno_address=args.noaddress
	gtags=args.tags
	gprefix_private_network_ip=args.prefixprivatenetworkip

def getIp(index):
	global ginitial_ip,gprefix_private_network_ip
	if gprefix_private_network_ip is not None:
		splitIp = gprefix_private_network_ip.split('.')
		ip=''
		if splitIp[0]=='10':
			ip="%s.%s.%s.%s" % (splitIp[0],splitIp[1],((index+ginitial_ip)/256 + int(splitIp[2])),((index+ginitial_ip)%(256)))
		return ip
	else:
		return ""

def get_config(index, image_response):
	global gprojectid, gnumbernodes, gnodeprefix, gzone, gmachine_type, gimage_family, gimage_project,gnetwork,gno_address, gtags, gprefix_private_network_ip
	machine_type = "zones/%s/machineTypes/%s" % (gzone,gmachine_type)
	source_disk_image = image_response['selfLink']
	network = "global/networks/%s" % gnetwork
	name= gnodeprefix + "-%s" % index
	ipaddress=getIp(index)
	config = {'name': name }
	config['machineType'] = machine_type

	config['disks'] = [{
                'boot': True,
                'autoDelete': True
                ,'initializeParams': {
                    'sourceImage': source_disk_image,
                }
            }]

	config['serviceAccounts'] = [{
            'email': 'default',
            'scopes': [
                'https://www.googleapis.com/auth/devstorage.read_write',
                'https://www.googleapis.com/auth/logging.write'
            ]
        }]
	if gtags is not None:
		config['tags'] = {
			"items": [
				"internal"
			]
		}    
	networkInterfaces = []
	networkInterfaceDict = {'network': network}
	if gprefix_private_network_ip is not None:
		networkInterfaceDict['networkIP'] = ipaddress
	if not gno_address:
		accesConfigs = []
		externalDict ={'name': 'External NAT'}
		externalDict['type'] =  'ONE_TO_ONE_NAT'
		accesConfigs.append(externalDict)
		networkInterfaceDict['accessConfigs'] = accesConfigs
	networkInterfaces.append(networkInterfaceDict)
	config['networkInterfaces']=networkInterfaces
	
	return config

def save_data(request_id, response, exception):
	global gjsonoutput
	if exception is not None:
		print exception
		pass
		# Do something with the exception
  	else:
  		gjsonoutput[response['name']]=response
  		pass
    	# Do something with the response
    	# gjsonoutput[response['name']]=response

def log_result(data):
	with open('log_create.txt', 'w') as outfile:
		json.dump(data, outfile)

def main():
	global gjsonoutput
	get_arguments()
	credentials = GoogleCredentials.get_application_default()
	compute = discovery.build('compute', 'v1', credentials=credentials)

	batch = compute.new_batch_http_request()
	batch_max=100
	image_response = compute.images().getFromFamily(project=gimage_project, family=gimage_family).execute()
	for i in range(1,gnumbernodes+1):
		config = get_config(i,image_response)
		batch.add(compute.instances().insert(project=gprojectid,zone=gzone,body=config),callback=save_data)
		if i % batch_max == 0:
			batch.execute()
			batch = compute.new_batch_http_request()
	batch.execute()
	log_result(gjsonoutput)
main()
