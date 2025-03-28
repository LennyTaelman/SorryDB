import Lake
open Lake DSL

package «mock_lean_repository» where
  -- add package configuration options here

lean_lib «MockLeanRepository» where
  -- add library configuration options here

@[default_target]
lean_exe «mock_lean_repository» where
  root := `Main
