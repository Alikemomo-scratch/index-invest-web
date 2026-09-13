## Bug Analysis: FundDB dates shifted one day earlier

### 1. Root Cause Category

- **Category**: E - Implicit Assumption
- **Specific Cause**: The provider emits millisecond timestamps for midnight in
  Asia/Shanghai. Converting them directly to a UTC calendar date shifts every
  observation to the previous day.

### 2. Why Fixes Failed

1. The initial parser used the repository's existing UTC timestamp pattern,
   which is correct for Yahoo but not for this provider.
2. Unit fixtures initially started at UTC midnight, so they could not expose the
   provider's local-midnight boundary behavior. Live verification revealed it.

### 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
| --- | --- | --- | --- |
| P0 | Architecture | Give the FundDB adapter an explicit UTC+8 timezone constant | DONE |
| P0 | Test coverage | Fixture uses 16:00 UTC on the prior day and expects the next China calendar date | DONE |
| P1 | Documentation | Record timestamp units and timezone in the backend source contract | DONE |

### 4. Systematic Expansion

- **Similar Issues**: Any provider timestamp parsed with a shared UTC assumption.
- **Design Improvement**: Keep timezone conversion inside each source adapter;
  downstream services consume ISO dates only.
- **Process Improvement**: Compare the first and last parsed dates with the
  provider's visible dates during every new live-adapter smoke test.

### 5. Knowledge Capture

- [x] Updated the backend index-research source contract.
- [x] Added a provider-boundary regression test.
- [x] Kept the analysis with the Trellis task.

