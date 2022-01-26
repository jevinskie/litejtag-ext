#!/usr/bin/env python3

#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2019 msloniewski <marcin.sloniewski@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse

from migen import *
from litex_boards.platforms import deca

from litex.soc.cores.clock import Max10PLL
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores.video import VideoDVIPHY
from litex.soc.cores.led import LedChaser
from litex.soc.cores.bitbang import I2CMaster

from liteeth.phy.mii import LiteEthPHYMII

from litescope import LiteScopeAnalyzer

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, with_usb_pll=False):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_hdmi   = ClockDomain()
        self.clock_domains.cd_usb    = ClockDomain()

        # # #

        # Clk / Rst.
        clk50 = platform.request("clk50")

        # PLL
        self.submodules.pll = pll = Max10PLL(speedgrade="-6")
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(clk50, 50e6)
        pll.create_clkout(self.cd_sys,  sys_clk_freq)
        pll.create_clkout(self.cd_hdmi, 40e6)

        # USB PLL.
        if with_usb_pll:
            ulpi  = platform.request("ulpi")
            self.comb += ulpi.cs.eq(1) # Enable ULPI chip to enable the ULPI clock.
            self.submodules.usb_pll = pll = Max10PLL(speedgrade="-6")
            self.comb += pll.reset.eq(self.rst)
            pll.register_clkin(ulpi.clk, 60e6)
            pll.create_clkout(self.cd_usb, 60e6, phase=-120) # -120° from DECA's example (also validated with LUNA).

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self,
                 sys_clk_freq=int(100e6),
                 with_led_chaser     = True,
                 with_video_terminal = False,
                 with_jtagbone       = False,
                 with_uartbone       = False,
                 with_ethernet       = False,
                 with_etherbone      = False,
                 eth_ip              = "192.168.43.50",
                 eth_dynamic_ip      = False,
                 with_analyzer       = False,
                 **kwargs):
        self.platform = platform = deca.Platform()

        # Defaults to JTAG-UART since no hardware UART.
        if kwargs["uart_name"] == "serial":
            kwargs["uart_name"] = "crossover"

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq,
            ident         = "LiteX SoC on Terasic DECA",
            ident_version = True,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = self.crg = _CRG(platform, sys_clk_freq, with_usb_pll=False)

        # Video ------------------------------------------------------------------------------------
        if with_video_terminal:
            self.submodules.videophy = VideoDVIPHY(platform.request("hdmi"), clock_domain="hdmi")
            self.add_video_terminal(phy=self.videophy, timings="800x600@60Hz", clock_domain="hdmi")

        # Jtagbone ---------------------------------------------------------------------------------
        if with_jtagbone:
            self.add_jtagbone()

        # UARTbone
        if with_uartbone:
            self.add_uartbone(name="gpio_serial", baudrate=3_000_000)

        # Ethernet
        if with_ethernet or with_etherbone:
            self.platform.toolchain.additional_sdc_commands += [
                'create_clock -name eth_rx_clk -period 40.0 [get_ports {eth_clocks_rx}]',
                'create_clock -name eth_tx_clk -period 40.0 [get_ports {eth_clocks_tx}]',
                'set_false_path -from [get_clocks {sys_clk}] -to [get_clocks {eth_rx_clk}]',
                'set_false_path -from [get_clocks {sys_clk}] -to [get_clocks {eth_tx_clk}]',
                'set_false_path -from [get_clocks {eth_rx_clk}] -to [get_clocks {eth_tx_clk}]',
            ]
            eth_clock_pads = self.platform.request("eth_clocks")
            eth_pads = self.platform.request("eth")
            self.submodules.ethphy = LiteEthPHYMII(
                clock_pads = eth_clock_pads,
                pads       = eth_pads)
            if with_ethernet:
                self.add_ethernet(phy=self.ethphy, dynamic_ip=eth_dynamic_ip)
            if with_etherbone:
                self.add_etherbone(phy=self.ethphy, ip_address=eth_ip)

        # Analyzer ---------------------------------------------------------------------------------
        if with_analyzer:
            analyzer_signals = list({
                *self.jtagbone_phy.jtag._signals_recursive,
                *self.jtagbone_phy.jtag.tap_fsm._signals_recursive,
            })
            analyzer_signals = list(set(analyzer_signals) - {
                self.jtagbone_phy.jtag.altera_reserved_tck,
                self.jtagbone_phy.jtag.altera_reserved_tms,
                self.jtagbone_phy.jtag.altera_reserved_tdi,
                self.jtagbone_phy.jtag.altera_reserved_tdo,
            })
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
                depth        = 4096,
                clock_domain = "sys",
                register     = True,
                csr_csv      = "analyzer.csv")

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            self.submodules.leds = LedChaser(
                pads         = platform.request_all("user_led"),
                sys_clk_freq = sys_clk_freq)

# Build --------------------------------------------------------------------------------------------

def argparse_set_def(parser: argparse.ArgumentParser, dst: str, default):
    changed = False
    for a in parser._actions:
        if dst == a.dest:
            a.default = default
            return
    raise ValueError(f'dest var {dst} arg not found')

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on DECA")
    parser.add_argument("--build",               action="store_true", help="Build bitstream")
    parser.add_argument("--load",                action="store_true", help="Load bitstream")
    parser.add_argument("--sys-clk-freq",        default=100e6,       help="System clock frequency (default: 50MHz)")
    parser.add_argument("--with-video-terminal", action="store_true", help="Enable Video Terminal (VGA)")
    parser.add_argument("--with-jtagbone",       action="store_true", help="Enable JTAGbone support")
    parser.add_argument("--with-uartbone",       action="store_true", help="Enable UARTbone support")
    ethopts = parser.add_mutually_exclusive_group()
    ethopts.add_argument("--with-ethernet",      action="store_true", help="Enable Ethernet support")
    ethopts.add_argument("--with-etherbone",     action="store_true", help="Enable Etherbone support")
    parser.add_argument("--eth-ip",              default="192.168.43.50", type=str, help="Ethernet/Etherbone IP address")
    parser.add_argument("--eth-dynamic-ip",      action="store_true", help="Enable dynamic Ethernet IP addresses setting")
    parser.add_argument("--with-analyzer",       action="store_true", help="Enable Analyzer support")
    builder_args(parser)
    soc_core_args(parser)
    argparse_set_def(parser, 'csr_csv', 'csr.csv')
    args = parser.parse_args()

    soc = BaseSoC(
        sys_clk_freq             = int(float(args.sys_clk_freq)),
        with_video_terminal      = args.with_video_terminal,
        with_jtagbone            = args.with_jtagbone,
        with_uartbone            = args.with_uartbone,
        with_ethernet            = args.with_ethernet,
        with_etherbone           = args.with_etherbone,
        eth_ip                   = args.eth_ip,
        eth_dynamic_ip           = args.eth_dynamic_ip,
        with_analyzer            = args.with_analyzer,
        **soc_core_argdict(args)
    )
    builder = Builder(soc, **builder_argdict(args))
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".sof"))

if __name__ == "__main__":
    main()
