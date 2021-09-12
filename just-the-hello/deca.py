#!/usr/bin/env python3

# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause


import os
import argparse

from migen import *
from migen.genlib.cdc import AsyncResetSynchronizer


from litex_boards.platforms import terasic_deca
from litex_boards.targets.terasic_deca import _CRG

from litex.build.altera.common import AlteraAsyncResetSynchronizer
from litex.build.altera.quartus import AlteraQuartusToolchain

from litex.soc.cores.clock import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.gen.fhdl import verilog

from litejtag_ext.hello import JTAGHello
from litex.soc.cores.jtag import JTAGPHY, MAX10JTAG, JTAGTAPFSM

# Bench SoC ----------------------------------------------------------------------------------------

class BenchSoC(SoCCore):
    def __init__(self, with_jtagbone=False, with_uartbone=False, with_analyzer=False, sys_clk_freq=int(100e6)):
        platform = terasic_deca.Platform()

        # SoCMini ----------------------------------------------------------------------------------
        SoCMini.__init__(self, platform, clk_freq=sys_clk_freq,
            ident          = "LiteJTAG Just Hello on MAX10 DECA",
            ident_version  = True
        )

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)


        if with_jtagbone:
            # Jtagbone -----------------------------------------------------------------------------
            self.add_jtagbone()
        else:
            # JTAG Hello ---------------------------------------------------------------------------
            platform.add_reserved_jtag_decls()
            reserved_pads = platform.get_reserved_jtag_pads()
            self.submodules.jtag_phy = MAX10JTAG(chain=1, reserved_pads=reserved_pads)

            self.clock_domains.cd_jtag = ClockDomain()
            self.comb += ClockSignal("jtag").eq(self.jtag_phy.tck)
            self.specials += AsyncResetSynchronizer(self.cd_jtag, ResetSignal("sys"))

            self.hello_tdo = hello_tdo = Signal()
            self.submodules.jtag_hello = JTAGHello(self.jtag_phy.tmsutap, self.jtag_phy.tckutap, self.jtag_phy.tdiutap,
                                                   hello_tdo, ResetSignal("sys"), self.jtag_phy)
            self.comb += self.jtag_phy.tdo.eq(hello_tdo)

        # UARTBone ---------------------------------------------------------------------------------
        if with_uartbone:
            self.add_uartbone(name="gpio_serial", baudrate=3_000_000)

        # scope ------------------------------------------------------------------------------------
        if with_analyzer:
            from litescope import LiteScopeAnalyzer

            if with_analyzer:
                jtag_phy = self.jtagbone_phy.jtag
            else:
                jtag_phy = self.jtag_phy
            jtag_phy.do_finalize()
            jtag_phy_sigs = jtag_phy._signals_recursive
            jtag_phy_sigs.remove(jtag_phy.altera_reserved_tdo) # wont pass fitter, output must go to pin
            jtag_phy_sigs.remove(jtag_phy.tdocore)

            if hasattr(self, 'jtag_hello'):
                hello_sigs = self.jtag_hello._signals_recursive
            else:
                hello_sigs = []

            analyzer_signals = [
                *jtag_phy_sigs,
                *hello_sigs,
            ]
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
                                                         depth=512,
                                                         clock_domain="sys",
                                                         register=True,
                                                         csr_csv="analyzer.csv")

        # LEDs -------------------------------------------------------------------------------------
        from litex.soc.cores.led import LedChaser
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)

class JTAGHelloTop(Module):
    def __init__(self, tms, tck, tdi, tdo):
        reserved_pads = Record([
            ('altera_reserved_tms', tms),
            ('altera_reserved_tck', tck),
            ('altera_reserved_tdi', tdi),
            ('altera_reserved_tdo', tdo),
        ],
            name='altera_jtag_reserved',
        )
        self.submodules.jtag_phy = MAX10JTAG(chain=1, reserved_pads=reserved_pads)

        self.clock_domains.cd_jtag = ClockDomain()
        self.comb += ClockSignal("jtag").eq(self.jtag_phy.tck)
        self.specials += AsyncResetSynchronizer(self.cd_jtag, ResetSignal("sys"))

        self.hello_tdo = hello_tdo = Signal()
        self.submodules.jtag_hello = JTAGHello(self.jtag_phy.tmsutap, self.jtag_phy.tckutap, self.jtag_phy.tdiutap,
                                               hello_tdo, ResetSignal("sys"), self.jtag_phy)
        self.comb += self.jtag_phy.tdo.eq(hello_tdo)


# Main ---------------------------------------------------------------------------------------------

def main():
    # platform.add_reserved_jtag_decls()
    # reserved_pads = platform.get_reserved_jtag_pads()jt
    altera_reserved_tms = Signal()
    altera_reserved_tck = Signal()
    altera_reserved_tdi = Signal()
    altera_reserved_tdo = Signal()
    jtag_hello_top = JTAGHelloTop(altera_reserved_tms, altera_reserved_tck, altera_reserved_tdi, altera_reserved_tdo)

    print(verilog.convert(jtag_hello_top,
                          {altera_reserved_tms, altera_reserved_tck, altera_reserved_tdi, altera_reserved_tdo},
                          special_overrides = {AsyncResetSynchronizer: AlteraAsyncResetSynchronizer},
    ))


if __name__ == "__main__":
    main()
