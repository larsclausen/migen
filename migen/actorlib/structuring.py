from migen.fhdl.structure import *
from migen.flow.actor import *

def _rawbits_layout(l):
	if isinstance(l, int):
		return [("rawbits", l)]
	else:
		return l

class Cast(CombinatorialActor):
	def __init__(self, layout_from, layout_to):
		CombinatorialActor.__init__(self,
			("sink", Sink, _rawbits_layout(layout_from)),
			("source", Source, _rawbits_layout(layout_to)))
	
	def get_process_fragment(self):
		sigs_from = self.token("sink").flatten()
		sigs_to = self.token("source").flatten()
		if sum(len(s) for s in sigs_from) != sum(len(s) for s in sigs_to):
			raise TypeError
		return Fragment([
			Cat(*sigs_to).eq(Cat(*sigs_from))
		])

def pack_layout(l, n):
	return [("chunk{0}".format(i), l) for i in range(n)]

class Unpack(Actor):
	def __init__(self, n, layout_to):
		self.n = n
		Actor.__init__(self,
			("sink", Sink, pack_layout(layout_to, n)),
			("source", Source, layout_to))
	
	def get_fragment(self):
		mux = Signal(max=self.n)
		last = Signal()
		comb = [
			last.eq(mux == (self.n-1)),
			self.endpoints["source"].stb.eq(self.endpoints["sink"].stb),
			self.endpoints["sink"].ack.eq(last & self.endpoints["source"].ack)
		]
		sync = [
			If(self.endpoints["source"].stb & self.endpoints["source"].ack,
				If(last,
					mux.eq(0)
				).Else(
					mux.eq(mux + 1)
				)
			)
		]
		cases = {}
		for i in range(self.n):
			cases[i] = [Cat(*self.token("source").flatten()).eq(Cat(*self.token("sink").subrecord("chunk{0}".format(i)).flatten()))]
		comb.append(Case(mux, cases).makedefault())
		return Fragment(comb, sync)

class Pack(Actor):
	def __init__(self, layout_from, n):
		self.n = n
		Actor.__init__(self,
			("sink", Sink, layout_from),
			("source", Source, pack_layout(layout_from, n)))
	
	def get_fragment(self):
		demux = Signal(max=self.n)
		
		load_part = Signal()
		strobe_all = Signal()
		cases = {}
		for i in range(self.n):
			cases[i] = [Cat(*self.token("source").subrecord("chunk{0}".format(i)).flatten()).eq(*self.token("sink").flatten())]
		comb = [
			self.busy.eq(strobe_all),
			self.endpoints["sink"].ack.eq(~strobe_all | self.endpoints["source"].ack),
			self.endpoints["source"].stb.eq(strobe_all),
			load_part.eq(self.endpoints["sink"].stb & self.endpoints["sink"].ack)
		]
		sync = [
			If(self.endpoints["source"].ack,
				strobe_all.eq(0)
			),
			If(load_part,
				Case(demux, cases),
				If(demux == (self.n - 1),
					demux.eq(0),
					strobe_all.eq(1)
				).Else(
					demux.eq(demux + 1)
				)
			)
		]
		return Fragment(comb, sync)
