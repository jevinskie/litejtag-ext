source [find interface/ftdi/tigard-jtag.cfg]

#verify_ircapture disable
#verify_jtag disable

#adapter speed 10000

ftdi_tdo_sample_edge falling
adapter speed 25000
# adapter speed 1000

source [find fpga/altera-10m50.cfg]

gdb_port disabled
tcl_port disabled
telnet_port disabled

puts "scan_chain: [scan_chain]"

#proc jtag_init {} {
#	puts "jtag_init called"
#}

init


runtest 16

# puts "Waiting for Any Key"
# gets stdin

irscan 10m50.tap 0xe

puts "Waiting for Any Key"
gets stdin

puts "  DEADBEEF 32 RES: 0x[drscan 10m50.tap 32 0xDEADBEEF]"

puts "00DEADBEEF 40 RES: 0x[drscan 10m50.tap 40 0x00DEADBEEF]"

puts "00DEADBEEF 64 RES: 0x[drscan 10m50.tap 64 0x00000000DEADBEEF]"

puts "00DEADBEEF 80 RES: 0x[drscan 10m50.tap 80 0x000000000000DEADBEEF]"

shutdown
