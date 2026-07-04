# Sprint1 Build008

## Delivered
- Tokyo Koibito PDF parser calibrated to visible invoice layout
- Tokyo Koibito Excel parser
- PostgreSQL connection helper
- RequestRepository
- Request Employee database schema
- Tokyo-specific single-pair CLI

## Known limitations
- Parser is calibrated to current Tokyo Koibito invoice format.
- OCR fallback is still not implemented.
- PostgreSQL save is implemented as repository but not yet wired into CLI by default.
