def lcs(x, y):
    """
    Compute the length of the Longest Common Subsequence between two sequences.
    """
    m = len(x)
    n = len(y)
    
    # Create a 2D array to store lengths of LCS
    L = [[0] * (n + 1) for i in range(m + 1)]
    
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 or j == 0:
                L[i][j] = 0
            elif x[i-1] == y[j-1]:
                L[i][j] = L[i-1][j-1] + 1
            else:
                L[i][j] = max(L[i-1][j], L[i][j-1])
                
    return L[m][n]

def calculate_rouge_l(candidate: str, reference: str) -> float:
    """
    Calculate ROUGE-L F1 score based on LCS.
    This is a simplified implementation tokenizing by space.
    """
    if not candidate or not reference:
        return 0.0
        
    # Simple tokenization
    cand_tokens = candidate.strip().split()
    ref_tokens = reference.strip().split()
    
    if not cand_tokens or not ref_tokens:
        return 0.0
        
    lcs_len = lcs(cand_tokens, ref_tokens)
    
    # Precision and Recall
    prec = lcs_len / len(cand_tokens) if len(cand_tokens) > 0 else 0
    rec = lcs_len / len(ref_tokens) if len(ref_tokens) > 0 else 0
    
    # F1 Score
    if (prec + rec) == 0:
        return 0.0
        
    f1 = 2 * ((prec * rec) / (prec + rec))
    return f1
