'''
    Instruction/Data optimization class
'''
import copy
import array
import re

import idc
import idautils
import idaapi

import Instruction
import Assembler

debug = 0
debug_detailed = 0

class MiscError(Exception):
    def __init__(self):
        return


class DeadCodeElimination:
    """Dead Instruction Elimination"""
    
    def __init__(self, function):
        self.function = function

    def ReduceBB(self, bb):
        if type(bb).__name__ == "generator":
            bb = list(bb)
        
        if len(bb) < 1:
            return False
        
        remove_todo = []
        
        for offset in xrange(0, len(bb)):
            taint = bb[offset].GetTaintInfo()
            if taint == None:
                continue                
            instr = bb[offset]

            if debug:
                print ">DeadCodeElimination:ReduceBB - @ [%08x] %s" % (instr.GetOriginEA(), instr.GetDisasm())
            
            if instr.IsCFI():
                if debug:
                    print ">DeadCodeElimination:ReduceBB - skipping CFI..."
                continue
            
            regs_to_check = {}
            regs_todo = 0
            skip_this = 0
            for op in taint.GetDstTaints():
                if op['type'] == 1:
                    if debug and debug_detailed:
                        print ">DeadCodeElimination:ReduceBB - DST# [%s:%d]" % (op['opnd'], op['type'])
                        
                    reg = taint.GetExOpndRegisters(op['opnd'])
                    
                    if len(reg) != 1:
                        if debug and debug_detailed:
                            print ">DeadCodeElimination:ReduceBB - !GetExOpndRegisters returned suspicious data"
                            print ">DeadCodeElimination:ReduceBB - ", op['opnd']
                            print ">DeadCodeElimination:ReduceBB - ", reg
                        
                        skip_this = 1
                        #raise MiscError
                        
                    else:
                        regs_to_check[reg[0][0]] = reg[0][1]
                        regs_todo += 1
                
                elif op['type'] in [2,3,4]:
                    skip_this = 1
                    
                elif op['type'] == None:
                    print ">DeadCodeElimination:ReduceBB - DST# [%s:None]" % (op['opnd'])
                    raise MiscError
                
                else:
                    #well if it taints any other source we let it live :)
                    if debug:
                        print ">DeadCodeElimination:ReduceBB - OP Type [%d] skipped @ [%08x]" % (op['type'], instr.GetOriginEA())
                    skip_this = 1
                
            if skip_this:
                if debug:
                    print ">DeadCodeElimination:ReduceBB - skipping..."
                continue
            
            flags_to_check = {}
            flags_todo = 0
            
            flags = taint.GetFlags('modif_f')
            if flags != None:
                for flag in flags:
                    flags_to_check[flag] = None
                    flags_todo += 1
            
            if debug and debug_detailed:
                print ">DeadCodeElimination:ReduceBB - Regs4Check-> ", regs_to_check
                print ">DeadCodeElimination:ReduceBB - Flags4Check-> ", flags_to_check
            
            #for delta in xrange(offset+1, len(block_taint)):
                #delta_taint = block_taint[delta]
            
            for delta in xrange(offset+1, len(bb)):
                delta_taint = bb[delta].GetTaintInfo()
                if delta_taint == None:
                    break
                
                if bb[delta].IsCFI():
                    if debug:
                        print ">DeadCodeElimination:ReduceBB - Found CFI instruction, skipping"
                        
                    break
                
                if debug and debug_detailed:
                    print ">DeadCodeElimination:ReduceBB - ", len(bb), delta, bb[delta].GetDisasm()
                
                if flags_todo > 0:
                    if delta_taint.GetFlags("modif_f") != None:
                        for flag in delta_taint.GetFlags("modif_f"):
                            if flags_to_check.has_key(flag):
                                flags_to_check[flag] = False
                                flags_todo -= 1
                                
                                if debug and debug_detailed:
                                    print ">DeadCodeElimination:ReduceBB - FOUND MODIF FLAG: adding False"
                    
                    if delta_taint.GetFlags("test_f") != None:
                        for flag in delta_taint.GetFlags("test_f"):
                            if flags_to_check.has_key(flag):
                                flags_to_check[flag] = True
                                flags_todo = 0
                                
                                if debug and debug_detailed:
                                    print ">DeadCodeElimination:ReduceBB - FOUND TESTF FLAG: adding True"
                                
                                break
                
                if regs_todo > 0:
                    
                    for op in delta_taint.GetDstTaints():
                        if op['type'] == 1:
                            regs = taint.GetExOpndRegisters(op['opnd'])
                            
                            for reg in regs:
                                if regs_to_check.has_key(reg[0]) and regs_to_check[reg[0]] != False and regs_to_check[reg[0]] <= reg[1]:
                                    regs_to_check[reg[0]] = False
                                    
                                    if debug and debug_detailed:
                                        print ">DeadCodeElimination:ReduceBB - FOUND DSTtaint False", reg
                                    
                                    regs_todo -= 1
                                    
                        elif op['type'] == 3 or op['type'] == 4:
                            regs = taint.GetExOpndRegisters(op['opnd'])
                            
                            for reg in regs:
                                if regs_to_check.has_key(reg[0]) and regs_to_check[reg[0]] <= reg[1]:
                                    regs_to_check[reg[0]] = True
                                    regs_todo = 0
                                    
                                    if debug and debug_detailed:
                                        print ">DeadCodeElimination:ReduceBB - FOUND DSTtaint True", reg[0]
                                    
                                    break
                    
                    for op in delta_taint.GetSrcTaints():
                        if op['type'] != None:
                            regs = taint.GetExOpndRegisters(op['opnd'])
                            
                            for reg in regs:
                                if regs_to_check.has_key(reg[0]) and regs_to_check[reg[0]] <= reg[1]:
                                    regs_to_check[reg[0]] = True
                                    regs_todo = 0
                                    
                                    if debug and debug_detailed:
                                        print ">DeadCodeElimination:ReduceBB - FOUND SRCtaint True", reg[0]
                                    
                                    break
                        else:
                            if debug and debug_detailed:
                                print ">DeadCodeElimination:ReduceBB - SRC# [%s:None]" % (op['opnd'])
                            raise MiscError
                            
                        
                if regs_todo == 0 and flags_todo == 0:
                    break
                    
            if regs_todo != 0 or flags_todo != 0:
                #let it live
                continue
            
            else:
                remove = 0
                for key in regs_to_check.iterkeys():
                    if regs_to_check[key] == True:
                        remove += 1
                        break
                
                for key in flags_to_check.iterkeys():
                    if flags_to_check[key] == True:
                        remove += 1
                        break
                
                if remove == 0:
                    #removing instruction
                    if debug:
                        print ">DeadCodeElimination:ReduceBB - Adding instruction to removal queue [%s] @ [%08x]" % (instr.GetDisasm(), instr.GetOriginEA())
                    
                    remove_todo.append(instr.GetOriginEA())
                    
        for item in remove_todo:
            if debug:
                print ">DeadCodeElimination:ReduceBB - REMOVING INSTRUCTION @[%08x]" % (item)
            self.function.RemoveInstruction(item)
            
        if len(remove_todo) > 0:
            return True
        else:
            return False
            
    def OptimizeFunction(self, function=None):
        if function:
            self.function = function
        
        modified = False
        for bb_ea in self.function.DFSFalseTraverseBlocks():
            if debug:
                print ">DeadCodeElimination:OptimizeFunction - DeadCode @ block [%08x]" % bb_ea
                
            modified |= self.ReduceBB(self.function.GetBBInstructions(bb_ea))
            
        return modified

class PeepHole:
    """Predefined optimization rules"""
    
    def __init__(self, function):
        self.function = function
            
    
    def RET2JMP(self, bb):
        if type(bb).__name__ == "generator":
            bb = list(bb)
        
        if len(bb) < 1:
            return False
        
        instr = bb[-1]
        modified = False
        
        if instr.GetMnem().lower().find("ret") >= 0:
            for (ref, path) in self.function.GetRefsFrom(instr.GetOriginEA()):
                if ref != None:
                    if debug:
                        print ">PeepHole:RET2JMP - Found fake RET @ [%08x]" % instr.GetOriginEA()
                        print ">PeepHole:RET2JMP - Replacing RET with [JMP %08xh]" % ref
                    
                    instr.SetMnem("jmp")
                    instr.SetComment("-replaced[RET]")
                    instr.SetDisasm("jmp %08xh" % ref)
                    instr.SetOpcode('\xeb\xef')
                    instr.SetIsModified(True)
                    
                    find_push = bb[-2]
                    if find_push.GetMnem().lower() == "push":
                        self.function.RemoveInstruction(find_push.GetOriginEA(), bb[0].GetOriginEA())
                        #for testing, upper one is faster :)
                        #self.function.RemoveInstruction(find_push.GetOriginEA())
                        
                        modified = True
                        
                        if debug:
                            print "RET2JMP: Removig PUSH from "
                            
        return modified
    
    def SymetricNOP(self, bb):
        if type(bb).__name__ == "generator":
            bb = list(bb)
            
        if len(bb) < 1:
            return False
        
        bb_len = len(bb)
        to_remove = []
        
        modified = False
        
        for offset in xrange(0, bb_len-1):
            mnem = bb[offset].GetMnem().lower()
            if mnem in ["mov", "xchg"]:
                instr = bb[offset]
                if instr.GetOpnd(1) == instr.GetOpnd(2):
                    if debug:
                        print ">PeepHole:SymetricNOP - Removing SYMETRIC @ [%08x] [%s] [%s %s]" % (instr.GetOriginEA(), instr.GetMnem(), instr.GetOpnd(1), instr.GetOpnd(2))
                    
                    instr.SetDisasm("NOP")
                    
                    instr.SetMnem("NOP")
                    instr.SetOpcode('\x90')
                    instr.SetOpnd(None, 1)
                    instr.SetOpnd(None, 2)
                    modified = True
                
        return modified

    def Shifts(self, bb):
        if type(bb).__name__ == "generator":
            bb = list(bb)
            
        if len(bb) < 1:
            return False
        
        bb_len = len(bb)
        to_remove = []
        
        modified = False
        
        for offset in xrange(0, bb_len-1):
            mnem = bb[offset].GetMnem().lower()
            if mnem in ["shr", "shl", "sar", "sal"]:
                instr = bb[offset]
                if instr.GetOpndType(2) == 5:
                    shift = instr.GetOpndValue(2)
                    real_shift = shift & 0x1f
                    
                    if real_shift == 0:
                        if debug:
                            print ">PeepHole:Shifts - Removing nop shift instr @ [%08x] [%s] [%s %s]" % (instr.GetOriginEA(), instr.GetMnem(), instr.GetOpnd(1), instr.GetOpnd(2))
                    
                        instr.SetDisasm("NOP")
                    
                        instr.SetMnem("NOP")
                        instr.SetOpcode('\x90')
                        instr.SetOpnd(None, 1)
                        instr.SetOpnd(None, 2)
                        modified = True
                        
                    elif real_shift != shift:
                        if debug:
                            print ">PeepHole:Shifts - Modifying shift argument instr @ [%08x] [%s] [%s %s] -> [%s %s]" % (instr.GetOriginEA(), instr.GetMnem(), instr.GetOpnd(1), instr.GetOpnd(2), instr.GetOpnd(1), hex(real_shift))
                        
                        instr.SetOpnd(hex(real_shift), 2)
                        instr.SetOpndValue(real_shift, 2)
                        modified = True
                
        return modified

    def PUSHPOP(self, bb):
        if type(bb).__name__ == "generator":
            bb = list(bb)
            
        if len(bb) < 1:
            return False
        
        bb_len = len(bb)
        to_remove = []
        
        for offset in xrange(0, bb_len-1):
            mnem = bb[offset].GetMnem().lower()
            if mnem == "push":                
                push = bb[offset]
                push_type = push.GetOpndType(1)
                
                if bb[offset+1].GetMnem().lower() == "pop":
                    if debug:
                        print ">PeepHole:PUSHPOP - Trying to remove PUSHPOP @ [%08x] [%s]" % (bb[offset].GetOriginEA(), bb[offset].GetMnem())
                    
                    pop = bb[offset+1]
                    pop_type = pop.GetOpndType(1)
                    
                    if push_type == pop_type and push_type == 1:
                        if push.GetOpnd(1) == pop.GetOpnd(1):
                            if debug:
                                print ">PeepHole:PUSHPOP - Removing PUSHPOP same reg [%08x] reg[%s]" % (bb[offset].GetOriginEA(), bb[offset].GetOpnd(1))
                            to_remove.append(push.GetOriginEA())
                            to_remove.append(pop.GetOriginEA())
                            
                            break
                        
                        elif push.GetOpnd(1).lower() in ['cs', 'ds', 'es', 'ss']:
                            continue
                        
                        else:
                            if push.GetRegSize(push.GetOpnd(1)) == pop.GetRegSize(pop.GetOpnd(1)):
                                pop.SetMnem("mov")
                                
                                pop.SetOpnd(pop.GetOpnd(1), 1)
                                pop.SetOpnd(push.GetOpnd(1), 2)
                                
                                pop.SetOpndType(1, 1)
                                pop.SetOpndType(1, 2)
                                
                                pop.SetDisasm("mov %s, %s" % (pop.GetOpnd(1), push.GetOpnd(1)))
                                
                                pop.SetOpcode(Assembler.SimpleAsm(pop.GetDisasm()))
                                if debug:
                                    print ">PeepHole:PUSHPOP - miasm:FAILED asm(%s) [%s]" % (pop.GetDisasm(), pop.GetOpcode().encode('hex'))
                                    
                                pop.SetOpndType(push.GetOpndType(1), 2)
                                pop.SetOpndValue(push.GetOpndValue(1), 2)
                                
                                to_remove.append(push.GetOriginEA())
                            
                                break
                            
                            else:
                                break
                            
                    if pop.GetOpcode()[0] == '\x66' and push.GetOpcode()[0] != '\x66':
                        if pop.GetOpcode()[0] != push.GetOpcode()[0]:
                            if debug:
                                print ">PeepHole:PUSHPOP - FAILING on \\x66 opcode [%s]/[%s]!" % (push.GetOpcode()[0].encode('hex'), pop.GetOpcode()[0].encode('hex'))
                            continue
                    
                    
                    if push_type in [2,3,4] and pop.GetOpndType(1) in [2,3,4]:
                        if debug:
                            print ">PeepHole:PUSHPOP - FAILING on PUSH/POP types!"
                        continue
                    
                    if debug:
                        print ">PeepHole:PUSHPOP - Removing PUSH/POP pair [%s]/[%s]" % (push.GetDisasm(), pop.GetDisasm())
                    to_remove.append(push.GetOriginEA())
                    
                    if push_type == 2:
                        dis_text = "MOV %s, [%09xh]" % (pop.GetOpnd(1), push.GetOpndValue(1))
                        dis_text = dis_text.replace('SMALL', '')
                        pop.SetDisasm(dis_text)
                    else:
                        dis_text = "MOV %s, %s" % (pop.GetOpnd(1), push.GetOpnd(1))
                        dis_text = dis_text.replace('SMALL', '')
                        pop.SetDisasm(dis_text)
                    
                    pop.SetMnem("MOV")
                    pop.SetOpnd(pop.GetOpnd(1), 1)
                    pop.SetOpnd(push.GetOpnd(1), 2)
                    
                    pop.SetOpcode(Assembler.SimpleAsm(pop.GetDisasm()))
                    pop.SetOpndType(push.GetOpndType(1), 2)
                    pop.SetOpndValue(push.GetOpndValue(1), 2)
                    
                    #pop.SetOpcode('\xba\x85')
                
                else:
                    for ins in bb[offset+1:]:
                        if ins.GetMnem() == "pop":
                            if debug:
                                print ">PeepHole:PUSHPOP - Removing PUSHPOP @ [%08x] [%s]" % (bb[offset].GetOriginEA(), bb[offset].GetMnem())
                            
                            pop = ins
                            
                            if push.GetOpndType(1) in [2,3,4] and pop.GetOpndType(1) in [2,3,4]:
                                break
                            
                            if pop.GetOpcode()[0] == '\x66' or push.GetOpcode()[0] != '\x66':
                                if pop.GetOpcode()[0] != push.GetOpcode()[0]:
                                    break
                                
                            to_remove.append(push.GetOriginEA())
                            
                            if push_type == 2:
                                dis_text = "MOV %s, [%09xh]" % (pop.GetOpnd(1), push.GetOpndValue(1))
                                dis_text = dis_text.replace('SMALL', '')
                                
                            else:
                                dis_text = "MOV %s, %s" % (pop.GetOpnd(1), push.GetOpnd(1))
                                dis_text = dis_text.replace('SMALL', '')
                            
                            pop.SetDisasm(dis_text)
                            
                            pop.SetMnem("MOV")
                            pop.SetOpnd(pop.GetOpnd(1), 1)
                            pop.SetOpnd(push.GetOpnd(1), 2)
                            
                            #pop.SetOpcode(Assembler.SimpleAsm(pop.GetDisasm()))
                            pop.SetOpndType(push.GetOpndType(1), 2)
                            pop.SetOpndValue(push.GetOpndValue(1), 2)
                            
                            pop.SetOpcode('\xba\x85')
                            
                            break
                        
                        taint = ins.GetTaintInfo()
                        if not taint:
                            break
                        
                        skip_this = 0
                        for op in taint.GetDstTaints():
                            if op['type'] == 1:
                                reg = taint.GetExOpndRegisters(op['opnd'])
                                if len(reg) != 1:
                                    if debug and debug_detailed:
                                        print ">PeepHole:PUSHPOP - !GetExOpndRegisters returned suspicious data"
                                        print ">PeepHole:PUSHPOP - ", op['opnd']
                                        print ">PeepHole:PUSHPOP - ", reg
                                        
                                    skip_this = 1
                                    break
                                
                                if reg[0][0] == "ESP":
                                    skip_this = 1
                                    break
                                
                                elif push_type == 1 and reg[0][0] == push.GetOpnd(1).upper():
                                    skip_this = 1
                                    break
                                
                            elif push_type in [2,3,4] and op['type'] in [2,3,4]:
                                skip_this = 1
                                break
                                
                        if skip_this == 1:
                            break
                            
                        
                        skip_this = 0
                        for op in taint.GetSrcTaints():
                            if op['type'] == 1:
                                reg = taint.GetExOpndRegisters(op['opnd'])
                                if len(reg) != 1:
                                    if debug and debug_detailed:
                                        print ">PeepHole:PUSHPOP - !GetExOpndRegisters returned suspicious data"
                                        print ">PeepHole:PUSHPOP - ", op['opnd']
                                        print ">PeepHole:PUSHPOP - ", reg
                                    skip_this = 1
                                    break
                                
                                if reg[0][0] == "ESP":
                                    skip_this = 1
                                    break
                                
                        if skip_this == 1:
                            break
                        
                    
            elif mnem == 'pushf' or mnem == 'pushfd' or mnem == 'pushfw':
                pushf = bb[offset]
                
                for ins in bb[offset+1:]:
                    i_mnem = ins.GetMnem()
                    if (i_mnem == 'popf' or i_mnem == 'popfd' or i_mnem == 'popfw') and i_mnem[3:] == mnem[4:]:
                        to_remove.append(ins.GetOriginEA())
                        to_remove.append(pushf.GetOriginEA())
                        
                        if debug:
                            print ">PeepHole:PUSHFPOPF - Removing %s[%08x]/%s[%08x] instructions" % (mnem, pushf.GetOriginEA(), i_mnem, ins.GetOriginEA())
                        
                    else:
                        i_taint = ins.GetTaintInfo()
                        if not i_taint:
                            break
                        
                        i_flags = i_taint.GetFlags('modif_f')
                        if i_flags != None and len(i_flags) > 0:
                            break
            
            elif mnem == 'pusha' or mnem == 'pushad':
                if len(bb) > (offset+1):
                    pusha = bb[offset]
                    
                    ins = bb[offset+1]
                    i_mnem = ins.GetMnem()
                    
                    if (i_mnem == 'popa' or i_mnem == 'popad') and mnem[4:] == i_mnem[3:]:
                        to_remove.append(ins.GetOriginEA())
                        to_remove.append(pusha.GetOriginEA())
                        
                        if debug:
                            print ">PeepHole:PUSHAPOPA - Removing %s[%08x]/%s[%08x] instructions" % (mnem, pusha.GetOriginEA(), i_mnem, ins.GetOriginEA())
            
            elif mnem == 'sub':
                sub = bb[offset]
                
                if sub.GetOpnd(1) == 'ESP' and sub.GetOpndValue(2) in [2,4]:
                    for ins in bb[offset+1:]:
                        if ins.GetMnem() == 'mov' and ins.GetOpndType(1) == 3 and ins.GetOpndType(2) == 5:
                            ins_disas = ins.GetDisasm()
                            if ins_disas.find('esp') > 0 and ( ins_disas.find('dword') > 0 or ins_disas.find('small') ):
                                
                                word_prefix = ''
                                if ins_disas.find('dword') > 0 and sub.GetOpndValue(2) == 4:
                                    dis_text = "PUSH DWORD %09xh" % ins.GetOpndValue(2)
                                    
                                elif ins_disas.find('word') > 0 and sub.GetOpndValue(2) == 2:
                                    dis_text = "PUSH WORD %07xh" % ins.GetOpndValue(2)
                                    word_prefix = '\x66'
                                    
                                else:
                                    if debug:
                                        print ">PeepHole:SUBPUSH - Skipping, operands sizes don't match"
                                        
                                    break
                                
                                ins.SetMnem("PUSH")
                                
                                ins.SetDisasm(dis_text)
                                
                                ins.SetOpnd(ins.GetOpnd(2), 1)
                                ins.SetOpndValue(ins.GetOpndValue(2), 1)
                                ins.SetOpndType(ins.GetOpndType(2), 1)
                                
                                ins.SetOpnd(None, 2)
                                ins.SetOpndType(None, 2)
                                ins.SetOpndValue(None, 2)
                                ins.SetOpndSize(None, 2)
                                
                                ins.SetOpcode(word_prefix + '\x68\xde\xad')
                                
                                to_remove.append(sub.GetOriginEA())
                                if debug:
                                    print ">PeepHole:SUBPUSH - Removing [%s][%08x] instructions" % (mnem, sub.GetOriginEA())
                                
                                break
                                
                        else:
                            #check that memory or stack isn't tainted
                            taint = ins.GetTaintInfo()
                            if not taint:
                                break
                            
                            skip_this = 0
                            for op in taint.GetDstTaints():
                                if op['type'] == 1:
                                    reg = taint.GetExOpndRegisters(op['opnd'])
                                    if len(reg) != 1:
                                        if debug and debug_detailed:
                                            print ">PeepHole:PUSHPOP - !GetExOpndRegisters returned suspicious data"
                                            print ">PeepHole:PUSHPOP - ", op['opnd']
                                            print ">PeepHole:PUSHPOP - ", reg
                                            
                                        skip_this = 1
                                        break
                                    
                                    if reg[0][0] == "ESP":
                                        skip_this = 1
                                        break
                                    
                                elif op['type'] in [2,3,4]:
                                    skip_this = 1
                                    break
                                    
                            if skip_this == 1:
                                break
                            
                            skip_this = 0
                            for op in taint.GetSrcTaints():
                                if op['type'] == 1:
                                    reg = taint.GetExOpndRegisters(op['opnd'])
                                    if len(reg) != 1:
                                        if debug and debug_detailed:
                                            print ">PeepHole:PUSHPOP - !GetExOpndRegisters returned suspicious data"
                                            print ">PeepHole:PUSHPOP - ", op['opnd']
                                            print ">PeepHole:PUSHPOP - ", reg
                                        skip_this = 1
                                        break
                                    
                                    if reg[0][0] == "ESP":
                                        skip_this = 1
                                        break
                                    
                            if skip_this == 1:
                                break
                            
        for item in to_remove:
            self.function.RemoveInstruction(item)
        
        if len(to_remove) > 0:
            return True
        else:
            return False

    def SymetricXCHG(self, bb):
        if type(bb).__name__ == "generator":
            bb = list(bb)
            
        if len(bb) < 1:
            return False
        
        bb_len = len(bb)
        to_remove = []
        
        modified = 0
        
        for offset in xrange(0, bb_len-1):
            mnem = bb[offset].GetMnem().lower()
            if mnem == "xchg":
                xchg = bb[offset]
                if (xchg.GetOpndType(1) != 1) or (xchg.GetOpndType(2) != 1):
                    continue
                
                next_symetric = 0
                if bb[offset+1].GetMnem() == "xchg":
                    xchg2 = bb[offset+1]
                    if ( (xchg2.GetOpnd(1) == xchg.GetOpnd(1)) and (xchg2.GetOpnd(2) == xchg.GetOpnd(2)) ) or ( (xchg2.GetOpnd(1) == xchg.GetOpnd(2)) and (xchg2.GetOpnd(2) == xchg.GetOpnd(1)) ):
                        
                        if debug:
                            print ">PeepHole:SymetricXCHG - Removing PUSHPOP @ [%08x] [%s]" % (bb[offset].GetOriginEA(), bb[offset].GetMnem())
                        
                        to_remove.append(xchg.GetOriginEA())
                        
                        instr = xchg
                        instr.SetDisasm("NOP")
                        instr.SetMnem("NOP")
                        instr.SetOpcode('\x90')
                        instr.SetOpnd(None, 1)
                        instr.SetOpnd(None, 2)
                        
                        instr = xchg2
                        instr.SetDisasm("NOP")
                        instr.SetMnem("NOP")
                        instr.SetOpcode('\x90')
                        instr.SetOpnd(None, 1)
                        instr.SetOpnd(None, 2)
                        
                        modified = True
                        next_symetric = 1
                
                if next_symetric == 0:
                    regs_to_check = {}
                    
                    xchg_taint = xchg.GetTaintInfo()
                    if not xchg_taint:
                        break
                    reg = xchg_taint.GetExOpndRegisters(xchg.GetOpnd(1))
                    
                    if len(reg[0][0]) == 0:
                        print ">PeepHole:SymetricXCHG - Got register len 0 [%s] [%08x]" % (xchg.GetDisasm(), xchg.GetOriginEA())
                        raise MiscError
                    
                    regs_to_check[reg[0][0]] = ''
                    
                    reg = xchg_taint.GetExOpndRegisters(xchg.GetOpnd(2))
                    
                    if len(reg[0][0]) == 0:
                        print ">PeepHole:SymetricXCHG - Got register len 0 [%s] [%08x]" % (xchg.GetDisasm(), xchg.GetOriginEA())
                        raise MiscError
                    
                    regs_to_check[reg[0][0]] = ''
                    
                    for ins in bb[offset+1:]:
                        if ins.GetMnem() == "xchg":
                            xchg2 = ins
                            if ( (xchg2.GetOpnd(1) == xchg.GetOpnd(1)) and (xchg2.GetOpnd(2) == xchg.GetOpnd(2)) ) or ( (xchg2.GetOpnd(1) == xchg.GetOpnd(2)) and (xchg2.GetOpnd(2) == xchg.GetOpnd(1)) ):
                                if debug:
                                    print ">PeepHole:SymetricXCHG - Removing PUSHPOP @ [%08x] [%s]" % (bb[offset].GetOriginEA(), bb[offset].GetMnem())
                                
                                instr = xchg
                                instr.SetDisasm("NOP")
                                instr.SetMnem("NOP")
                                instr.SetOpcode('\x90')
                                instr.SetOpnd(None, 1)
                                instr.SetOpnd(None, 2)
                                
                                instr = xchg2
                                instr.SetDisasm("NOP")
                                instr.SetMnem("NOP")
                                instr.SetOpcode('\x90')
                                instr.SetOpnd(None, 1)
                                instr.SetOpnd(None, 2)
                                
                                modified = True
                                break
                        
                        taint = ins.GetTaintInfo()
                        if not taint:
                            skip_this = 1
                            break
                        
                        skip_this = 0
                        for op in taint.GetDstTaints():
                            if op['type'] == 1:
                                regs = taint.GetExOpndRegisters(op['opnd'])
                                
                                for reg in regs:
                                    if regs_to_check.has_key(reg[0]):
                                        if debug and debug_detailed:
                                            print ">PeepHole:SymetricXCHG - FOUND DSTtaint: Breaking optimization for previous XCHG instruction", reg
                                        skip_this = 1                                
                                
                        if skip_this == 1:
                            break
                            
                        for op in taint.GetSrcTaints():
                            if op['type'] == 1:
                                regs = taint.GetExOpndRegisters(op['opnd'])
                                
                                for reg in regs:
                                    if regs_to_check.has_key(reg[0]):
                                        if debug and debug_detailed:
                                            print ">PeepHole:SymetricXCHG - FOUND SRCtaint: Breaking optimization for previous XCHG instruction", reg
                                        skip_this = 1  
                                
                        if skip_this == 1:
                            break
                        
                    if skip_this == 1:
                        skip_this = 0
                        continue
        
        if modified:
            return True
        else:
            return False

    def ReduceBB(self, bb):
        optimization_order = ['PUSHPOP', 'RET2JMP', 'SymetricNOP', 'Shifts', 'SymetricXCHG']
        #optimization_order = ['RET2JMP']
        
        modified = False
        for optimization in optimization_order:
            modified |= getattr(self, optimization)(bb)
            
        return modified

    
    def OptimizeFunction(self, function=None):
        if function:
            self.function = function
        
        modified = False
        for bb_ea in self.function.DFSFalseTraverseBlocks():
            modified |= self.ReduceBB(list(self.function.GetBBInstructions(bb_ea)))
            
        return modified
