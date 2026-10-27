// Print the p-code of the instructions at the given word addresses of the first memory block.
// Script args: <hex word address>...
//@category Testing
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.pcode.*;
public class DumpPcode extends GhidraScript {
	protected void run() throws Exception {
		for (String a : getScriptArgs()) {
			AddressSpace cs = currentProgram.getAddressFactory().getDefaultAddressSpace();
			Address ad = cs.getAddress(Long.parseLong(a, 16) * cs.getAddressableUnitSize());
			disassemble(ad);
			Instruction i = getInstructionAt(ad);
			println("== " + ad + " " + i);
			for (PcodeOp op : i.getPcode()) {
				println("   " + op);
			}
		}
	}
}
