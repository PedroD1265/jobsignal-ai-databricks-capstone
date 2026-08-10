"""Create the synthetic demo candidate profile used by screenshots and agent tests."""

import lakebase

if __name__ == "__main__":
    print(lakebase.seed_demo_profile())
