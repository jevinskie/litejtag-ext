source [find interface/altera-usb-blaster2.cfg]
#source [find fpga/altera-10m50.cfg]

if { [info exists CHIPNAME] } {
	set _CHIPNAME $CHIPNAME
} else {
	set _CHIPNAME 10mcl016
}

jtag newtap $_CHIPNAME tap -irlen 10 -expected-id 0x020f20dd


source [find cpld/jtagspi.cfg]


#gdb_port disabled
#tcl_port disabled
#telnet_port disabled

init

irscan 10mcl016.tap 0xe

puts "Waiting for Any Key"
gets stdin

puts "  DEADBEEF 32 RES: 0x[drscan 10mcl016.tap 32 0xDEADBEEF]"

puts "00DEADBEEF 40 RES: 0x[drscan 10mcl016.tap 40 0x00DEADBEEF]"

puts "00DEADBEEF 64 RES: 0x[drscan 10mcl016.tap 64 0x00000000DEADBEEF]"

puts "00DEADBEEF 80 RES: 0x[drscan 10mcl016.tap 80 0x000000000000DEADBEEF]"

shutdown
