import argparse
import json
from validation.run_result_validator import validate_output

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    print(json.dumps(validate_output(args.output_dir), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
