import tqdm
import logging
import argparse
from os import path

import lib.simos_flash_utils as simos_flash_utils
import lib.constants as constants

#Get an instance of logger, which we'll pull from the config file
logger = logging.getLogger("VWFlash")

logging.config.fileConfig(path.join(path.dirname(path.abspath(__file__)), 'logging.conf'))

logger.info("Starting VW_Flash.py")

#build a List of valid block parameters for the help message
block_number_help = []
for name, number in constants.block_name_to_int.items():
    block_number_help.append(name)
    block_number_help.append(str(number))

#Set up the argument/parser with run options
parser = argparse.ArgumentParser(description='VW_Flash CLI', 
    epilog="The MAIN CLI interface for using the tools herein")
parser.add_argument('--action', help="The action you want to take", 
    choices=['checksum', 'checksum_fix', 'checksum_ecm3', 'checksum_fix_ecm3', 'lzss', 'encrypt', 'prepare', 'flash_bin', 'flash_prepared'], required=True)
parser.add_argument('--infile',help="the absolute path of an inputfile", action="append")
parser.add_argument('--outfile',help="the absolutepath of a file to output", action="store_true")
parser.add_argument('--block', type=str, help="The block name or number", 
    choices=block_number_help, action="append", required=True)
parser.add_argument('--simos12', help="specify simos12, available for checksumming", action='store_true')

args = parser.parse_args()

#function that reads in from a file
def read_from_file(infile = None):
    f = open(infile, "rb")
    return f.read()

#function that writes out binary data to a file
def write_to_file(outfile = None, data_binary = None):
    if outfile and data_binary:
        with open(outfile, 'wb') as fullDataFile:
            fullDataFile.write(data_binary)

#if the number of block args doesn't match the number of file args, log it and exit
if len(args.block) != len(args.infile):
    logger.critical("You must specify a block for every infile")
    exit()

#convert --blocks on the command line into a list of ints
if args.block:
    blocks = [int(constants.block_to_number(block)) for block in args.block]

#build the dict that's used to proces the blocks
#  Everything is structured based on the following format:
#  {'infile1': {'blocknum': num, 'binary_data': binary},
#     'infile2: {'blocknum': num2, 'binary_data': binary2}
#  }
if args.infile and args.block:
    blocks_infile = {}
    for i in range(0, len(args.infile)):
        blocks_infile[args.infile[i]] = {'blocknum': blocks[i], 'binary_data': read_from_file(args.infile[i])}

#if there was no file specified, log it and exit
else:
    logger.critical("No input file specified, exiting")
    exit()

def callback_function(t, flasher_step, flasher_status, flasher_progress):
    t.update(flasher_progress - t.n)
    t.set_description(flasher_status, refresh=True)

#if statements for the various cli actions
if args.action == "checksum":
    simos_flash_utils.checksum(blocks_infile)

elif args.action == "checksum_fix":
    blocks_infile = simos_flash_utils.checksum_fix(blocks_infile)          

    #if outfile was specified in the arguments, go through the dict and write each block out
    if args.outfile:
        for filename in blocks_infile:
            binary_data = blocks_infile[filename]['binary_data']
            blocknum = blocks_infile[filename]['blocknum']
 
            write_to_file(data_binary = blocks_infile[filename]['binary_data'], 
                outfile = filename.rstrip(".bin") + ".checksummed_block" + str(blocknum) + ".bin")
    else:
        logger.critical("Outfile not specified, files not saved!!")

if args.action == "checksum_ecm3":
    simos_flash_utils.checksum_ecm3(blocks_infile)

elif args.action == "checksum_fix_ecm3":
    blocks_infile = simos_flash_utils.checksum_ecm3(blocks_infile, True)          

    #if outfile was specified in the arguments, go through the dict and write each block out
    if args.outfile:
        for filename in blocks_infile:
            binary_data = blocks_infile[filename]['binary_data']
            blocknum = blocks_infile[filename]['blocknum']
 
            write_to_file(data_binary = blocks_infile[filename]['binary_data'], 
                outfile = filename.rstrip(".bin") + ".checksummed_block" + str(blocknum) + ".bin")
    else:
        logger.critical("Outfile not specified, files not saved!!")

elif args.action == "lzss":
    simos_flash_utils.lzss_compress(blocks_infile, args.outfile)

elif args.action == "encrypt":
    blocks_infile = simos_flash_utils.encrypt_blocks(blocks_infile)

    #if outfile was specified, go through each block in the dict and write it out
    if args.outfile:
        for filename in blocks_infile:
            binary_data = blocks_infile[filename]['binary_data']
            blocknum = blocks_infile[filename]['blocknum']

            outfile = filename + ".flashable_block" + str(blocknum)
            logger.info("Writing encrypted file to: " + outfile)
            write_to_file(outfile = outfile, data_binary = binary_data)
    else:
        logger.critical("No outfile specified, skipping")


elif args.action == 'prepare':
    simos_flash_utils.prepareBlocks(blocks_infile)

elif args.action == 'flash_bin':
    logger.info("Executing flash_bin with the following blocks:\n" + 
      "\n".join([' : '.join([
           filename, 
           str(blocks_infile[filename]['blocknum']),
           constants.int_to_block_name[blocks_infile[filename]['blocknum']],
           str(blocks_infile[filename]['binary_data'][constants.software_version_location[blocks_infile[filename]['blocknum']][0]:constants.software_version_location[blocks_infile[filename]['blocknum']][1]])]) for filename in blocks_infile]))
    
    t = tqdm.tqdm(total = 100, colour='green')

    def wrap_callback_function(flasher_step, flasher_status, flasher_progress):
        callback_function(t, flasher_step, flasher_status, float(flasher_progress))

    simos_flash_utils.flash_bin(blocks_infile, wrap_callback_function)
    
    t.close()

elif args.action == 'flash_prepared':
    t = tqdm.tqdm(total = 100, colour='green')
    
    def wrap_callback_function(flasher_step, flasher_status, flasher_progress):
        callback_function(t, flasher_step, flasher_status, float(flasher_progress))
    
    simos_flash_utils.flash_prepared(blocks_infile, wrap_callback_function)
    
    t.close()
