-- two sorries on same line

/-- proofs
  first sorry: "exact Nat.le_refl n"
  second sorry: "exact Nat.zero_le 1"
-/


theorem ineq (n : Nat) : n + 1 ≥ n + 0 := by
  exact Nat.add_le_add (by sorry) (by sorry)

theorem ineq_solved (n : Nat) : n + 1 ≥ n + 0 := by
  exact Nat.add_le_add (by exact Nat.le_refl n) (by exact Nat.zero_le 1)
