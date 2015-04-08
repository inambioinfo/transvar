from transcripts import *
from utils import *
from record import *
from describe import *
from err import *

def annotate_snv_cdna(args, q, tpts, db):

    found = False
    for t in tpts:
        try:
            if q.tpt and t.name != q.tpt:
                raise IncompatibleTranscriptError('transcript id unmatched')
            t.ensure_seq()
            
            if (q.cpos() <= 0 or q.cpos() > t.cdslen()):
                raise IncompatibleTranscriptError()
            codon = t.cpos2codon((q.cpos()+2)/3)
            if not codon:
                raise IncompatibleTranscriptError()

            r = Record()
            r.chrm = t.chrm
            r.tname = t.format()
            r.gene = t.gene.name
            r.strand = t.strand

            r.gnuc_pos = t.tnuc2gnuc(q.pos)
            r.gnuc_ref = faidx.refgenome.fetch_sequence(t.chrm, r.gnuc_pos, r.gnuc_pos)
            if t.strand == '+':
                if q.ref and r.gnuc_ref != q.ref:
                    raise IncompatibleTranscriptError()
                r.gnuc_alt = q.alt if q.alt else ''
            else:
                if q.ref and r.gnuc_ref != complement(q.ref):
                    raise IncompatibleTranscriptError()
                r.gnuc_alt = complement(q.alt) if q.alt else ''

            r.tnuc_pos = q.pos
            r.tnuc_ref = r.gnuc_ref if t.strand == '+' else complement(r.gnuc_ref)
            r.tnuc_alt = q.alt

            db.query_dbsnp(r, t.chrm, r.gnuc_pos, r.gnuc_ref, r.gnuc_alt)
            r.reg = describe_genic_site(args, t.chrm, r.gnuc_pos, t, db)
            
            # coding region
            if q.pos.tpos == 0 and t.transcript_type == 'protein_coding':

                if (q.ref and q.ref != t.seq[q.cpos()-1]):
                    raise IncompatibleTranscriptError('SNV ref not matched')

                r.taa_ref = codon2aa(codon.seq)
                r.taa_pos = codon.index
                if not q.alt:
                    r.taa_alt = ''
                else:
                    mut_seq = list(codon.seq[:])
                    mut_seq[(q.cpos()-1) % 3] = q.alt
                    r.taa_alt = codon2aa(''.join(mut_seq))
                    if r.taa_ref != r.taa_alt:
                        r.append_info('missense')
                    elif r.taa_alt:
                        r.append_info('synonymous')
                    r.append_info('reference_codon=%s;alternative_codon=%s' % (codon.seq, ''.join(mut_seq)))
                
            else:  # coordinates are with respect to the exon boundary
                t.check_exon_boundary(q.pos)

        except IncompatibleTranscriptError:
            continue
        except UnknownChromosomeError:
            continue
        found = True
        r.format(q.op)

    if not found:
        r = Record()
        r.tnuc_pos = q.pos
        r.tnuc_ref = q.ref
        r.tnuc_alt = q.alt
        r.append_info('no_valid_transcript_found_(from_%s_candidates)' % len(tpts))
        r.format(q.op)

    return

def _annotate_snv_protein(args, q, t, db):

    """ find all the mutations given a codon position, yield records """

    if q.alt and q.alt not in reverse_codon_table:
        err_warn('unknown alternative: %s, ignore alternative.' % q.alt)
        q.alt = ''

    # when there's a transcript specification
    if q.tpt and t.name != q.tpt:
        raise IncompatibleTranscriptError('transcript id unmatched')

    t.ensure_seq()

    if (q.pos <= 0 or q.pos > t.cdslen()):
        raise IncompatibleTranscriptError('codon nonexistent')
    codon = t.cpos2codon(q.pos)
    if not codon:
        raise IncompatibleTranscriptError('codon nonexistent')

    # skip if reference amino acid is given
    # and codon sequence does not generate reference aa
    # codon.seq is natural sequence
    if q.ref and codon.seq not in aa2codon(q.ref):
        raise IncompatibleTranscriptError('reference amino acid unmatched')

    r = Record()
    r.chrm = t.chrm
    r.tname = t.format()

    # if alternative amino acid is given
    # filter the target mutation set to those give
    # the alternative aa
    
    if q.alt:
        tgt_codon_seqs = [x for x in aa2codon(q.alt) if x != codon.seq]
        diffs = [codondiff(x, codon.seq) for x in tgt_codon_seqs]
        diffinds = sorted(range(len(diffs)), key=lambda i: len(diffs[i]))

        # guessed mutation
        gi = diffinds[0]        # guessed diff index
        gdiff = diffs[gi]       # guessed diff
        gtgtcodonseq = tgt_codon_seqs[gi]
        if len(gdiff) == 1:
            nrefbase = codon.seq[gdiff[0]]
            naltbase = gtgtcodonseq[gdiff[0]]

            r.tnuc_pos = (codon.index-1)*3 + 1 + gdiff[0]
            r.tnuc_ref = nrefbase
            r.tnuc_alt = naltbase
            if codon.strand == '+':
                r.gnuc_ref = nrefbase
                r.gnuc_alt = naltbase
                r.gnuc_pos = codon.locs[gdiff[0]]
            else:
                r.gnuc_ref = complement(nrefbase)
                r.gnuc_alt = complement(naltbase)
                r.gnuc_pos = codon.locs[2-gdiff[0]]
        else:
            tnuc_beg = (codon.index-1)*3 + 1 + gdiff[0]
            tnuc_end = (codon.index-1)*3 + 1 + gdiff[-1]
            tnuc_ref = codon.seq[gdiff[0]:gdiff[-1]+1]
            tnuc_alt = gtgtcodonseq[gdiff[0]:gdiff[-1]+1]
            r.tnuc_range = '%d_%d%s>%s' % (tnuc_beg, tnuc_end, tnuc_ref, tnuc_alt)
            if codon.strand == '+':
                r.gnuc_range = '%d_%d%s>%s' % (codon.locs[gdiff[0]], codon.locs[gdiff[-1]],
                                               tnuc_ref, tnuc_alt)
            else:
                r.gnuc_range = '%d_%d%s>%s' % (codon.locs[2-gdiff[-1]],
                                               codon.locs[2-gdiff[0]],
                                               reverse_complement(tnuc_ref), 
                                               reverse_complement(tnuc_alt))
        # candidate mutations
        cdd_snv_muts = []
        cdd_mnv_muts = []
        for i in diffinds:
            if i == gi: continue
            diff = diffs[i]
            tgtcodonseq = tgt_codon_seqs[i]
            if len(diff) == 1:
                nrefbase = codon.seq[diff[0]]
                naltbase = tgtcodonseq[diff[0]]
                tnuc_pos = (codon.index-1)*3 + 1 + diff[0]
                tnuc_tok = 'c.%d%s>%s' % (tnuc_pos, nrefbase, naltbase)
                if codon.strand ==  '+':
                    gnuc_tok  = '%s:g.%d%s>%s' % (t.chrm, codon.locs[diff[0]],
                                                  nrefbase, naltbase)
                else:
                    gnuc_tok = '%s:g.%d%s>%s' % (t.chrm, codon.locs[2-diff[0]],
                                                 complement(nrefbase), complement(naltbase))
                cdd_snv_muts.append(gnuc_tok)
            else:
                tnuc_beg = (codon.index-1)*3 + 1 + diff[0]
                tnuc_end = (codon.index-1)*3 + 1 + diff[-1]
                tnuc_ref = codon.seq[diff[0]:diff[-1]+1]
                tnuc_alt = tgtcodonseq[diff[0]:diff[-1]+1]
                tnuc_tok = 'c.%d_%d%s>%s' % (tnuc_beg, tnuc_end, tnuc_ref, tnuc_alt)
                if codon.strand == '+':
                    gnuc_tok = '%s:g.%d_%d%s>%s' % (t.chrm, 
                                                    codon.locs[diff[0]],
                                                    codon.locs[diff[-1]],
                                                    tnuc_ref, tnuc_alt)
                else:
                    gnuc_tok = '%s:g.%d_%d%s>%s' % (t.chrm,
                                                    codon.locs[2-diff[-1]],
                                                    codon.locs[2-diff[0]],
                                                    reverse_complement(tnuc_ref),
                                                    reverse_complement(tnuc_alt))
                cdd_mnv_muts.append(gnuc_tok)

        r.append_info('reference_codon=%s;candidate_codons=%s' % (codon.seq, ','.join(tgt_codon_seqs)))
        if cdd_snv_muts:
            r.append_info('candidate_snv_variants=%s' % ','.join(cdd_snv_muts))
        if cdd_mnv_muts:
            r.append_info('candidate_mnv_variants=%s' % ','.join(cdd_mnv_muts))

        db.query_dbsnp_codon(r, t.chrm, codon)
    else:
        r.gnuc_range = '%d_%d' % (codon.locs[0], codon.locs[2])
        r.tnuc_range = '%d_%d' % ((codon.index-1)*3+1, (codon.index-1)*3+3)

    return r, codon

# used by codon search
def __core_annotate_codon_snv(args, q, db):
    for t in q.gene.tpts:
        try:
            r, c = _annotate_snv_protein(args, q, t, db)
        except IncompatibleTranscriptError:
            continue
        except SequenceRetrievalError:
            continue
        except UnknownChromosomeError:
            continue
        yield t, c

def annotate_snv_protein(args, q, tpts, db):

    found = False
    for t in tpts:
        try:
            r, c = _annotate_snv_protein(args, q, t, db)
        except IncompatibleTranscriptError as e:
            continue
        except SequenceRetrievalError as e:
            continue
        except UnknownChromosomeError as e:
            err_print(str(e))
            continue
        
        r.gene = t.gene.name
        r.strand = t.strand
        set_taa_snv(r, q.pos, q.ref, q.alt)
        r.reg = RegCDSAnno(t, c)
        r.format(q.op)
        found = True

    if not found:
        r = Record()
        set_taa_snv(r, q.pos, q.ref, q.alt)
        r.info = 'no_valid_transcript_found'
        r.format(q.op)


def annotate_snv_gdna(args, q, db):

    # check reference base
    gnuc_ref = faidx.refgenome.fetch_sequence(q.tok, q.pos, q.pos)
    if q.ref and gnuc_ref != q.ref:
        
        r = Record()
        r.chrm = q.tok
        r.pos = q.pos
        r.info = "invalid_reference_base_%s_(expect_%s)" % (q.ref, gnuc_ref)
        r.format(q.op)
        err_print("invalid reference base %s (expect %s), maybe wrong reference?" % (q.ref, gnuc_ref))
        return
    
    else:
        q.ref = gnuc_ref

    for reg in describe(args, q, db):

        r = Record()
        r.reg = reg
        r.chrm = q.tok
        r.gnuc_pos = q.pos
        r.pos = r.gnuc_pos
        r.gnuc_ref = gnuc_ref
        r.gnuc_alt = q.alt if q.alt else ''
        db.query_dbsnp(r, q.tok, q.pos, q.ref, q.alt if q.alt else None)
        
        if hasattr(reg, 't'):

            c,p = reg.t.gpos2codon(q.pos)

            r.tname = reg.t.format()
            r.gene = reg.t.gene.name
            r.strand = reg.t.strand
            r.tnuc_pos = p

            if c.strand == '+':
                r.tnuc_ref = r.gnuc_ref
                r.tnuc_alt = r.gnuc_alt
            else:
                r.tnuc_ref = complement(r.gnuc_ref)
                r.tnuc_alt = complement(r.gnuc_alt) if r.gnuc_alt else ''

            expt = r.set_splice()
            if p.tpos == 0 and reg.t.transcript_type=='protein_coding':
                if c.seq in standard_codon_table:
                    r.taa_ref = standard_codon_table[c.seq]
                    r.taa_pos = c.index

                    if q.alt:
                        if c.strand == '+':
                            alt_seq = set_seq(c.seq, c.locs.index(q.pos), q.alt)
                        else:
                            alt_seq = set_seq(c.seq, 2-c.locs.index(q.pos), complement(q.alt))

                        r.taa_alt = codon2aa(alt_seq)
                        if r.taa_alt != r.taa_ref:
                            r.append_info('missense')
                        elif r.taa_alt:
                            r.append_info('synonymous')

                else:
                    r.append_info('truncated_refseq_at_boundary_(codon_seq_%s_codon_index_%d_protein_length_%d)' % (c.seq, c.index, len(reg.t)/3))

                r.append_info('codon_pos=%s' % (c.locformat(),))
                r.append_info('ref_codon_seq=%s' % c.seq)
                
        r.format(q.op)

def set_taa_snv(r, pos, ref, alt):

    r.taa_pos = pos
    r.taa_ref = ref
    r.taa_alt = alt
    if r.taa_ref != r.taa_alt:
        r.append_info('missense')
    elif r.taa_ref:
        r.append_info('synonymous')
