-- triple of theorems with multiline proofs
-- to test sorry location matching in verify

/-- proof:
  rw [Nat.add_comm]
  rw [Nat.add_zero]
-/

theorem top (n : Nat) : n + 1 = 1 + n + 0 := by sorry

theorem middle (n : Nat) : n + 1 = 1 + n + 0 := by sorry

theorem bottom (n : Nat) : n + 1 = 1 + n + 0 := by sorry
