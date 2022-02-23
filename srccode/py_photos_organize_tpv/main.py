import sys
import time
import datetime
import argparse
import logging

parser = argparse.ArgumentParser(description='Script options parser.')

parser.add_argument('-o', '--files_orign', type=str, required=False, default='.\\resources\\input_files\\')
parser.add_argument('-d', '--files_destination', type=str, required=False, default='.\\resources\\output_files\\')
parser.add_argument('-p', '--files_prefix', type=str, required=False, default='%Y_%m_%d_%Hh%Mm%Ss')


args = parser.parse_args()

if __name__ == '__main__':

	# Getting arguments
	files_orign = args.files_orign
	files_destination = args.files_destination
	files_prefix = args.files_prefix

	# Create and configure logger
	logging.basicConfig(filename='py_photos_organize_tpv.log', format='%(asctime)s %(message)s', filemode='w')
	# Creating an object
	logger = logging.getLogger()

	# Setting the threshold of logger to DEBUG
	logger.setLevel(logging.DEBUG)

	# Test messages
	#logger.debug("Harmless debug Message")
	#logger.info("Just an information")
	#logger.warning("Its a Warning")
	#logger.error("Did you try to divide by zero")
	#logger.critical("Internet is down")
	logger.info('<< pyPhotosOrganizeTPV >>')
	logger.info('Starting script...')

	logger.info('Arguments:')
	logger.info('Files Orign: ' + files_orign)
	logger.info('Files Destination: '+ files_destination)
	logger.info('Files Prefix: '+ files_prefix)


	print('Files Orign (INPUT): ' + files_orign)
	print('Files Destination (OUTPUT): ' + files_destination)
	print('Show datetime in prefix format: ' + datetime.datetime.strftime(datetime.datetime.today() , files_prefix))

	sys.exit(0)