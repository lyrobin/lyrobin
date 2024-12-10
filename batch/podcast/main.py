import os


def main():
    print(os.environ.get("VARIABLE", "hello world"))


if __name__ == "__main__":
    main()
