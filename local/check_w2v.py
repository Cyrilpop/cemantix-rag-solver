from pathlib import Path

from src.engine.vocab import verify_w2v_file

p = Path("/app/cemantix_data/frWac_no_postag_phrase_500_cbow_cut10.bin")
print("taille:", p.stat().st_size)
print("verification:", verify_w2v_file(p))
