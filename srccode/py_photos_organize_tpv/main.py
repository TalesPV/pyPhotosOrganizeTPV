import os
import sys
import time
# Reference:  https://www.codevscolor.com/python-print-date-time-hour-minute
import datetime
import argparse
# Reference: https://pypi.org/project/coloredlogs/
# Reference: https://coloredlogs.readthedocs.io/en/latest/readme.html
# Reference: https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
import coloredlogs
# Reference: https://www.geeksforgeeks.org/logging-in-python/
import logging

parser = argparse.ArgumentParser(description='Script options parser.')

parser.add_argument('-o', '--files_orign', type=str, required=False, default='.\\resources\\input_files\\')
parser.add_argument('-d', '--files_destination', type=str, required=False, default='.\\resources\\output_files\\')
parser.add_argument('-p', '--files_prefix', type=str, required=False, default='%Y_%m_%d_%Hh%Mm%Ss')


args = parser.parse_args()

# Basic References:
# https://blog.gunderson.tech/26307/using-virtual-environment-requirements-txt-with-python

def main():
	# Getting arguments
	files_orign = args.files_orign
	files_destination = args.files_destination
	files_prefix = args.files_prefix


	# Create a logger object.
	logger = logging.getLogger(__name__)
	# Setting the threshold of logger to DEBUG
	logger.setLevel(logging.DEBUG)
	# Create and configure logger
	logging.basicConfig(
		filename='.\\tmp\\' + datetime.datetime.strftime(datetime.datetime.today(), '%Y_%m_%d_%Hh%Mm%Ss') + '-py_photos_organize_tpv.log', 
		format='%(asctime)s %(name)s [%(process)d] %(levelname)s %(message)s', 
		filemode='w'
	)

	# Reference: https://pypi.org/project/coloredlogs/
	coloredlogs.install(
		#level='DEBUG', 
		logger=logger, 
		milliseconds=True, 
		fmt='%(asctime)s,%(msecs)03d %(levelname)s %(message)s' 
	)

	logger.info('<< pyPhotosOrganizeTPV >>')

	logger.info('Starting script...')

	logger.info('Arguments:')
	logger.info('Files Orign (INPUT): ' + files_orign)
	logger.info('Files Destination (OUTPUT): ' + files_destination)
	logger.info('Files Prefix: '+ files_prefix)
	logger.info('Show datetime in prefix format: ' + datetime.datetime.strftime(datetime.datetime.today() , files_prefix))

	# TO_DO: 

	sys.exit(0)

if __name__ == '__main__':
	main()