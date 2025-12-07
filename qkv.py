import numpy as np
np.random.seed(42)

print("="*80)
print("COMPLETE TOKEN-BY-TOKEN WALKTHROUGH OF ATTENTION MECHANISM")
print("="*80)

# Setup
full_sentence = "The cat sat on the mat"
tokens = full_sentence.lower().split()
print(f"\nOriginal sentence: '{full_sentence}'")
print(f"After tokenization: {tokens}")
print(f"Number of tokens: {len(tokens)}")

# For this example, let's use first 3 tokens to keep it manageable
input_sentence = tokens[:3]
print(f"\nWe'll process: {input_sentence}")

# Build vocabulary from all tokens
vocab = list(set(tokens))  # unique tokens
vocab.sort()  # for consistency
print(f"\nComplete vocabulary: {vocab}")
print(f"Vocabulary size: {len(vocab)}")

embedding_dim = 4
d_k = d_v = 4  # Same as embedding_dim for simplicity!

print(f"\nHyperparameters:")
print(f"  Embedding dimension: {embedding_dim}")
print(f"  Q/K/V dimension: {d_k} (same as embedding dim!)")

print("\n" + "="*80)
print("STEP 1: TOKENIZATION - TEXT TO TOKENS")
print("="*80)
print(f"Input text:  '{full_sentence}'")
print(f"Split by spaces into tokens:")
for i, token in enumerate(tokens):
    print(f"  Token {i}: '{token}'")

print("\n" + "="*80)
print("STEP 2: BUILD VOCABULARY (ALL UNIQUE TOKENS)")
print("="*80)
print("Vocabulary (sorted alphabetically):")
for i, token in enumerate(vocab):
    in_input = "← USED IN INPUT" if token in input_sentence else ""
    print(f"  {i}: '{token}' {in_input}")

print("\n" + "="*80)
print("STEP 3: TOKEN TO INDEX MAPPING")
print("="*80)
token_to_idx = {token: idx for idx, token in enumerate(vocab)}
print("Creating a dictionary to map tokens to indices:")
for token, idx in token_to_idx.items():
    in_input = "← USED IN INPUT" if token in input_sentence else ""
    print(f"  '{token}' → {idx} {in_input}")

print(f"\nNow converting input sentence to indices:")
input_indices = [token_to_idx[token] for token in input_sentence]
for i, token in enumerate(input_sentence):
    idx = input_indices[i]
    print(f"  '{token}' → index {idx}")
print(f"\nInput indices array: {input_indices}")

print("\n" + "="*80)
print("STEP 4: INITIALIZE EMBEDDING MATRIX (RANDOM VALUES)")
print("="*80)
print(f"Creating embedding matrix of shape ({len(vocab)}, {embedding_dim})")
print(f"Each token gets a random {embedding_dim}-dimensional vector")
print()

embedding_matrix = np.random.randn(len(vocab), embedding_dim)

print(f"Embedding Matrix - Shape: {embedding_matrix.shape}")
print(f"(Each row = one token's embedding vector)\n")
print("Token         Index    Emb_0        Emb_1        Emb_2        Emb_3")
print("-" * 80)
for i, token in enumerate(vocab):
    in_input = " ← INPUT" if token in input_sentence else ""
    print(f"{token:12s}  {i:3d}   {embedding_matrix[i,0]:11.6f}  {embedding_matrix[i,1]:11.6f}  {embedding_matrix[i,2]:11.6f}  {embedding_matrix[i,3]:11.6f}{in_input}")

print("\n" + "="*80)
print("STEP 5: LOOKUP EMBEDDINGS FOR INPUT TOKENS")
print("="*80)
print(f"Input tokens: {input_sentence}")
print(f"Input indices: {input_indices}")
print()

X = embedding_matrix[input_indices]

print("Looking up each token's embedding from the embedding matrix:")
for i, token in enumerate(input_sentence):
    idx = input_indices[i]
    print(f"\n  Token '{token}' (index {idx}):")
    print(f"    Embedding vector: [{X[i,0]:.6f}, {X[i,1]:.6f}, {X[i,2]:.6f}, {X[i,3]:.6f}]")
    print(f"    (This is row {idx} from the embedding matrix)")

print(f"\n\nInput Embedding Matrix X - Shape: {X.shape}")
print("(sequence_length × embedding_dim) = (3 × 4)")
print()
print("      Token      Emb_0        Emb_1        Emb_2        Emb_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    print(f"[{i}]  {token:8s}  {X[i,0]:11.6f}  {X[i,1]:11.6f}  {X[i,2]:11.6f}  {X[i,3]:11.6f}")

print("\n" + "="*80)
print("STEP 6: INITIALIZE WEIGHT MATRICES (RANDOM - LEARNED DURING TRAINING)")
print("="*80)
print(f"These are now SQUARE matrices ({embedding_dim} × {embedding_dim})")
print(f"They transform {embedding_dim}-dim embeddings into {d_k}-dim Q/K/V vectors")
print()

W_Q = np.random.randn(embedding_dim, d_k)
W_K = np.random.randn(embedding_dim, d_k)
W_V = np.random.randn(embedding_dim, d_v)

print(f"W_Q (Query Weight Matrix) - Shape: {W_Q.shape}")
print("(embedding_dim × d_k) = (4 × 4) - SQUARE MATRIX")
print()
print("Input_dim    Q_out_0      Q_out_1      Q_out_2      Q_out_3")
print("-" * 80)
for i in range(embedding_dim):
    print(f"   {i}       {W_Q[i,0]:11.6f}  {W_Q[i,1]:11.6f}  {W_Q[i,2]:11.6f}  {W_Q[i,3]:11.6f}")

print(f"\n\nW_K (Key Weight Matrix) - Shape: {W_K.shape}")
print("(embedding_dim × d_k) = (4 × 4) - SQUARE MATRIX")
print()
print("Input_dim    K_out_0      K_out_1      K_out_2      K_out_3")
print("-" * 80)
for i in range(embedding_dim):
    print(f"   {i}       {W_K[i,0]:11.6f}  {W_K[i,1]:11.6f}  {W_K[i,2]:11.6f}  {W_K[i,3]:11.6f}")

print(f"\n\nW_V (Value Weight Matrix) - Shape: {W_V.shape}")
print("(embedding_dim × d_v) = (4 × 4) - SQUARE MATRIX")
print()
print("Input_dim    V_out_0      V_out_1      V_out_2      V_out_3")
print("-" * 80)
for i in range(embedding_dim):
    print(f"   {i}       {W_V[i,0]:11.6f}  {W_V[i,1]:11.6f}  {W_V[i,2]:11.6f}  {W_V[i,3]:11.6f}")

print("\n" + "="*80)
print("STEP 7: COMPUTE QUERY VECTORS (Q = X @ W_Q)")
print("="*80)
print(f"Multiplying input embeddings X ({X.shape}) by W_Q ({W_Q.shape})")
print(f"Result: Q with shape (3, 4) - same dimension as input!")
print()

Q = X @ W_Q

print("Computing Q for each token:\n")
for i, token in enumerate(input_sentence):
    print(f"Token '{token}':")
    print(f"  X[{i}] = [{X[i,0]:.6f}, {X[i,1]:.6f}, {X[i,2]:.6f}, {X[i,3]:.6f}]")
    print(f"  Q[{i}] = X[{i}] @ W_Q")
    print(f"  Calculation:")
    for j in range(d_k):
        calc_str = " + ".join([f"({X[i,k]:.4f} × {W_Q[k,j]:.4f})" for k in range(embedding_dim)])
        result = sum([X[i,k] * W_Q[k,j] for k in range(embedding_dim)])
        print(f"    Q[{i}][{j}] = {calc_str}")
        print(f"            = {result:.6f}")
    print(f"  Q[{i}] = [{Q[i,0]:.6f}, {Q[i,1]:.6f}, {Q[i,2]:.6f}, {Q[i,3]:.6f}]")
    print()

print("Query Matrix Q - Shape:", Q.shape)
print()
print("      Token      Q_0          Q_1          Q_2          Q_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    print(f"[{i}]  {token:8s}  {Q[i,0]:11.6f}  {Q[i,1]:11.6f}  {Q[i,2]:11.6f}  {Q[i,3]:11.6f}")

print("\n" + "="*80)
print("STEP 8: COMPUTE KEY VECTORS (K = X @ W_K)")
print("="*80)
print(f"Multiplying input embeddings X ({X.shape}) by W_K ({W_K.shape})")
print(f"Result: K with shape (3, 4) - same dimension as input!")
print()

K = X @ W_K

print("Computing K for each token:\n")
for i, token in enumerate(input_sentence):
    print(f"Token '{token}':")
    print(f"  X[{i}] = [{X[i,0]:.6f}, {X[i,1]:.6f}, {X[i,2]:.6f}, {X[i,3]:.6f}]")
    print(f"  K[{i}] = X[{i}] @ W_K")
    print(f"  Calculation:")
    for j in range(d_k):
        calc_str = " + ".join([f"({X[i,k]:.4f} × {W_K[k,j]:.4f})" for k in range(embedding_dim)])
        result = sum([X[i,k] * W_K[k,j] for k in range(embedding_dim)])
        print(f"    K[{i}][{j}] = {calc_str}")
        print(f"            = {result:.6f}")
    print(f"  K[{i}] = [{K[i,0]:.6f}, {K[i,1]:.6f}, {K[i,2]:.6f}, {K[i,3]:.6f}]")
    print()

print("Key Matrix K - Shape:", K.shape)
print()
print("      Token      K_0          K_1          K_2          K_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    print(f"[{i}]  {token:8s}  {K[i,0]:11.6f}  {K[i,1]:11.6f}  {K[i,2]:11.6f}  {K[i,3]:11.6f}")

print("\n" + "="*80)
print("STEP 9: COMPUTE VALUE VECTORS (V = X @ W_V)")
print("="*80)
print(f"Multiplying input embeddings X ({X.shape}) by W_V ({W_V.shape})")
print(f"Result: V with shape (3, 4) - same dimension as input!")
print()

V = X @ W_V

print("Computing V for each token:\n")
for i, token in enumerate(input_sentence):
    print(f"Token '{token}':")
    print(f"  X[{i}] = [{X[i,0]:.6f}, {X[i,1]:.6f}, {X[i,2]:.6f}, {X[i,3]:.6f}]")
    print(f"  V[{i}] = X[{i}] @ W_V")
    print(f"  Calculation:")
    for j in range(d_v):
        calc_str = " + ".join([f"({X[i,k]:.4f} × {W_V[k,j]:.4f})" for k in range(embedding_dim)])
        result = sum([X[i,k] * W_V[k,j] for k in range(embedding_dim)])
        print(f"    V[{i}][{j}] = {calc_str}")
        print(f"            = {result:.6f}")
    print(f"  V[{i}] = [{V[i,0]:.6f}, {V[i,1]:.6f}, {V[i,2]:.6f}, {V[i,3]:.6f}]")
    print()

print("Value Matrix V - Shape:", V.shape)
print()
print("      Token      V_0          V_1          V_2          V_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    print(f"[{i}]  {token:8s}  {V[i,0]:11.6f}  {V[i,1]:11.6f}  {V[i,2]:11.6f}  {V[i,3]:11.6f}")

print("\n" + "="*80)
print("STEP 10: COMPUTE ATTENTION SCORES (Q @ K.T)")
print("="*80)
print(f"Computing dot product between each Query and each Key")
print(f"Q shape: {Q.shape}, K.T shape: {K.T.shape}")
print(f"Result shape: (3, 3) - each token attends to every token")
print()

attention_scores = Q @ K.T

print("Detailed calculation of each attention score:\n")
for i, token_i in enumerate(input_sentence):
    print(f"Query for token '{token_i}' [position {i}]:")
    print(f"  Q[{i}] = [{Q[i,0]:.6f}, {Q[i,1]:.6f}, {Q[i,2]:.6f}, {Q[i,3]:.6f}]")
    print(f"  Computing attention to each token:")
    for j, token_j in enumerate(input_sentence):
        print(f"\n    Attention to '{token_j}' [position {j}]:")
        print(f"      K[{j}] = [{K[j,0]:.6f}, {K[j,1]:.6f}, {K[j,2]:.6f}, {K[j,3]:.6f}]")
        calc = " + ".join([f"({Q[i,k]:.4f} × {K[j,k]:.4f})" for k in range(d_k)])
        result = sum([Q[i,k] * K[j,k] for k in range(d_k)])
        products = [f"{Q[i,k]*K[j,k]:.6f}" for k in range(d_k)]
        print(f"      Q[{i}] · K[{j}] = {calc}")
        print(f"                  = {' + '.join(products)}")
        print(f"                  = {result:.6f}")
    print()

print("\nAttention Scores Matrix - Shape:", attention_scores.shape)
print("(Each row shows how one token attends to all tokens)")
print()
print("            K_the        K_cat        K_sat")
print("-" * 70)
for i, token in enumerate(input_sentence):
    print(f"Q_{token:3s}  {attention_scores[i,0]:13.6f}  {attention_scores[i,1]:13.6f}  {attention_scores[i,2]:13.6f}")

print("\nInterpretation:")
print(f"  Row 0: 'the' is querying all tokens")
print(f"  Row 1: 'cat' is querying all tokens")
print(f"  Row 2: 'sat' is querying all tokens")

print("\n" + "="*80)
print("STEP 11: SCALE ATTENTION SCORES (÷ √d_k)")
print("="*80)
scaling_factor = np.sqrt(d_k)
print(f"Scaling factor: √{d_k} = {scaling_factor:.6f}")
print("This prevents very large values going into softmax")
print()

scaled_scores = attention_scores / scaling_factor

print("Scaled scores for each position:\n")
for i, token in enumerate(input_sentence):
    print(f"Token '{token}' [position {i}]:")
    for j, token_j in enumerate(input_sentence):
        original = attention_scores[i,j]
        scaled = scaled_scores[i,j]
        print(f"  To '{token_j}': {original:.6f} ÷ {scaling_factor:.6f} = {scaled:.6f}")
    print()

print("Scaled Attention Scores Matrix - Shape:", scaled_scores.shape)
print()
print("            K_the        K_cat        K_sat")
print("-" * 70)
for i, token in enumerate(input_sentence):
    print(f"Q_{token:3s}  {scaled_scores[i,0]:13.6f}  {scaled_scores[i,1]:13.6f}  {scaled_scores[i,2]:13.6f}")

print("\n" + "="*80)
print("STEP 12: APPLY SOFTMAX TO GET ATTENTION WEIGHTS")
print("="*80)
print("Softmax converts scores to probabilities (0 to 1, sum to 1 per row)")
print()

def softmax(x):
    exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return exp_x / np.sum(exp_x, axis=-1, keepdims=True)

print("Softmax formula: softmax(x_i) = exp(x_i) / Σ exp(x_j)")
print()

attention_weights = softmax(scaled_scores)

print("Computing softmax for each row:\n")
for i, token in enumerate(input_sentence):
    print(f"Token '{token}' [position {i}]:")
    print(f"  Scaled scores: [{scaled_scores[i,0]:.6f}, {scaled_scores[i,1]:.6f}, {scaled_scores[i,2]:.6f}]")
    
    # Compute exponentials
    exps = np.exp(scaled_scores[i] - np.max(scaled_scores[i]))
    print(f"  Exponentials:  [{exps[0]:.6f}, {exps[1]:.6f}, {exps[2]:.6f}]")
    
    exp_sum = exps.sum()
    print(f"  Sum of exp:    {exp_sum:.6f}")
    
    print(f"  Probabilities: [{attention_weights[i,0]:.6f}, {attention_weights[i,1]:.6f}, {attention_weights[i,2]:.6f}]")
    print(f"  Sum:           {attention_weights[i].sum():.6f} (should be 1.0)")
    print()

print("Attention Weights Matrix - Shape:", attention_weights.shape)
print("(Probability distribution: each row sums to 1.0)")
print()
print("            K_the        K_cat        K_sat        Row_Sum")
print("-" * 80)
for i, token in enumerate(input_sentence):
    row_sum = attention_weights[i].sum()
    print(f"Q_{token:3s}  {attention_weights[i,0]:13.6f}  {attention_weights[i,1]:13.6f}  {attention_weights[i,2]:13.6f}  {row_sum:13.6f}")

print("\n" + "="*80)
print("STEP 13: COMPUTE FINAL OUTPUT (attention_weights @ V)")
print("="*80)
print("Each token's output is a weighted sum of all Value vectors")
print("Output dimension = 4 (same as input embedding dimension!)")
print()

output = attention_weights @ V

print("Computing output for each token:\n")
for i, token in enumerate(input_sentence):
    print(f"Token '{token}' [position {i}]:")
    print(f"  Attention weights: [{attention_weights[i,0]:.6f}, {attention_weights[i,1]:.6f}, {attention_weights[i,2]:.6f}]")
    print(f"  Output = weighted sum of all V vectors:")
    
    for j, token_j in enumerate(input_sentence):
        weight = attention_weights[i,j]
        print(f"    + {weight:.6f} × V[{j}] ({token_j})")
        print(f"    + {weight:.6f} × [{V[j,0]:.6f}, {V[j,1]:.6f}, {V[j,2]:.6f}, {V[j,3]:.6f}]")
        print(f"    = [{weight*V[j,0]:.6f}, {weight*V[j,1]:.6f}, {weight*V[j,2]:.6f}, {weight*V[j,3]:.6f}]")
    
    print(f"  Final output[{i}] = [{output[i,0]:.6f}, {output[i,1]:.6f}, {output[i,2]:.6f}, {output[i,3]:.6f}]")
    print()

print("Final Output Matrix - Shape:", output.shape)
print("(This is what gets passed to the next layer)")
print("(Same shape as input X! 3 tokens × 4 dimensions)")
print()
print("      Token      Out_0        Out_1        Out_2        Out_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    print(f"[{i}]  {token:8s}  {output[i,0]:11.6f}  {output[i,1]:11.6f}  {output[i,2]:11.6f}  {output[i,3]:11.6f}")

print("\n" + "="*80)
print("COMPARISON: INPUT vs OUTPUT")
print("="*80)
print("\nINPUT EMBEDDINGS (X):")
print("      Token      Emb_0        Emb_1        Emb_2        Emb_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    print(f"[{i}]  {token:8s}  {X[i,0]:11.6f}  {X[i,1]:11.6f}  {X[i,2]:11.6f}  {X[i,3]:11.6f}")

print("\nOUTPUT (AFTER ATTENTION):")
print("      Token      Out_0        Out_1        Out_2        Out_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    print(f"[{i}]  {token:8s}  {output[i,0]:11.6f}  {output[i,1]:11.6f}  {output[i,2]:11.6f}  {output[i,3]:11.6f}")

print("\nDIFFERENCE (Output - Input):")
print("      Token      Δ_0          Δ_1          Δ_2          Δ_3")
print("-" * 80)
for i, token in enumerate(input_sentence):
    diff = output[i] - X[i]
    print(f"[{i}]  {token:8s}  {diff[0]:11.6f}  {diff[1]:11.6f}  {diff[2]:11.6f}  {diff[3]:11.6f}")

print("\n" + "="*80)
print("COMPLETE SUMMARY OF ALL MATRICES")
print("="*80)
print(f"\nInput:")
print(f"  Tokens: {input_sentence}")
print(f"  X (embeddings): {X.shape} = (3 tokens × 4 dimensions)")
print(f"\nWeight Matrices (learned during training) - ALL SQUARE:")
print(f"  W_Q: {W_Q.shape} = (4 × 4)")
print(f"  W_K: {W_K.shape} = (4 × 4)")
print(f"  W_V: {W_V.shape} = (4 × 4)")
print(f"\nProjected Matrices (same dimensions as input!):")
print(f"  Q (queries): {Q.shape} = (3 tokens × 4 dims)")
print(f"  K (keys):    {K.shape} = (3 tokens × 4 dims)")
print(f"  V (values):  {V.shape} = (3 tokens × 4 dims)")
print(f"\nAttention:")
print(f"  Attention scores:  {attention_scores.shape} = (3 × 3)")
print(f"  Attention weights: {attention_weights.shape} = (3 × 3)")
print(f"\nOutput:")
print(f"  Output: {output.shape} = (3 tokens × 4 dims) - SAME AS INPUT!")
print("\n" + "="*80)
print("KEY INSIGHT:")
print("Since d_k = d_v = embedding_dim = 4:")
print("  - All weight matrices are SQUARE (4×4)")
print("  - Q, K, V have the SAME dimensions as input X")
print("  - Output has the SAME dimensions as input X")
print("  - This makes the attention layer a 'dimension-preserving' transformation")
print("="*80)