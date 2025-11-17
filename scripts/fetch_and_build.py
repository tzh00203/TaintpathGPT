import os
import argparse
import csv
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up paths
THIS_SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = THIS_SCRIPT_DIR.parent
sys.path.append(str(ROOT_DIR))

from src.config import DATA_DIR

def fetch_and_build_one(payload):
    """Fetch and optionally build a single project."""
    (project, no_build, try_all, jdk, mvn, gradle, gradlew, use_container, verbose, language) = payload
    project_slug = project[1]

    print(f"\n== Processing {project_slug} ({language}) ==")

    # Step 1: Fetch
    print(f"== Fetching {project_slug} ==")
    fetch_cmd = ["python3", f"{ROOT_DIR}/scripts/fetch_one.py", project_slug]
    if use_container:
        fetch_cmd.append("--from-container")
    if verbose:
        fetch_cmd.append("--verbose")

    result = subprocess.run(fetch_cmd, capture_output=not verbose, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to fetch {project_slug}")
        if not verbose:
            print(result.stdout)
            print(result.stderr)
        return False
    print(f"== Done fetching {project_slug} ==")

    if no_build or use_container:
        return True

    # Step 2: Build (language specific)
    if language == "java":
        print(f"== Building {project_slug} (Java) ==")
        build_cmd = ["python3", f"{ROOT_DIR}/scripts/build_one.py", project_slug]
        if try_all:
            build_cmd.append("--try_all")
        if jdk:
            build_cmd.extend(["--jdk", jdk])
        if mvn:
            build_cmd.extend(["--mvn", mvn])
        if gradle:
            build_cmd.extend(["--gradle", gradle])
        if gradlew:
            build_cmd.append("--gradlew")

        result = subprocess.run(build_cmd, capture_output=not verbose, text=True)
        if result.returncode != 0:
            print(f"❌ Failed to build {project_slug}")
            if not verbose:
                print(result.stdout)
                print(result.stderr)
            return False

    elif language == "python":
        print(f"== Preparing {project_slug} (Python) ==")
        project_dir = Path(f"{DATA_DIR}/project-sources") / project_slug

        if not project_dir.exists():
            print(f"❌ Source directory not found: {project_dir}")
            return False

        # Python 不需要 build，只做依赖准备
        req_file = project_dir / "requirements.txt"
        if req_file.exists():
            print("📦 Installing dependencies...")
            try:
                subprocess.run(
                    ["pip", "install", "-r", str(req_file)],
                    cwd=project_dir,
                    check=True,
                    capture_output=not verbose,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Dependency installation failed (ignored): {e}")
        else:
            print("ℹ️ No requirements.txt found, skipping dependency install")

        print("✅ Python project ready for CodeQL analysis (no build needed)")

    else:
        print(f"⚠️ Unknown language: {language}")
        return False

    print(f"✅ Done processing {project_slug}")
    return True



def parallel_fetch_and_build(projects, no_build, try_all, jdk, mvn, gradle, gradlew, use_container, verbose, language):
    """Process multiple projects in parallel."""
    results = []
    failed_projects = []

    with ThreadPoolExecutor() as executor:
        future_to_project = {
            executor.submit(fetch_and_build_one, (project, no_build, try_all, jdk, mvn, gradle, gradlew, use_container, verbose, language)): project
            for project in projects
        }

        for future in as_completed(future_to_project):
            project = future_to_project[future]
            project_slug = project[1]
            try:
                success = future.result()
                results.append(success)
                if not success:
                    failed_projects.append(project_slug)
            except Exception as exc:
                print(f'⚠️  Project {project_slug} generated an exception: {exc}')
                failed_projects.append(project_slug)
                results.append(False)

    print("\n====== Summary ======")
    successful = sum(results)
    total = len(projects)
    print(f"✅ Successfully processed: {successful}/{total}")
    if failed_projects:
        print(f"❌ Failed projects: {', '.join(failed_projects)}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch and build projects (Java/Python)")
    parser.add_argument("--language", type=str, choices=["java", "python"], default="java",
                        help="Language of the project (default: java)")
    parser.add_argument("--no-build", action="store_true", help="Only fetch projects, skip build")
    parser.add_argument("--try_all", action="store_true", help="Try all build configurations (Java only)")
    parser.add_argument("--use-container", action="store_true", help="Fetch from prebuilt container, skip build")
    parser.add_argument("--verbose", action="store_true", help="Show detailed logs")
    parser.add_argument("--jdk", type=str, help="Specify JDK version")
    parser.add_argument("--mvn", type=str, help="Specify Maven version")
    parser.add_argument("--gradle", type=str, help="Specify Gradle version")
    parser.add_argument("--gradlew", action="store_true", help="Use project gradlew script")
    parser.add_argument("--filter", nargs="+", type=str, help="Filter projects by name substring")
    parser.add_argument("--exclude", nargs="+", type=str, help="Exclude projects by name substring")
    parser.add_argument("--cwe", nargs="+", type=str, help="Filter by CWE type")

    args = parser.parse_args()

    # Load project info
    with open(f"{DATA_DIR}/project_info.csv", 'r') as f:
        reader = list(csv.reader(f))[1:]

    projects = filter_projects(reader, args)
    if not projects:
        print("No matching projects found.")
        return 0

    print(f"====== Processing {len(projects)} {args.language.upper()} Projects ======")

    parallel_fetch_and_build(
        projects, args.no_build, args.try_all, args.jdk, args.mvn,
        args.gradle, args.gradlew, args.use_container, args.verbose, args.language
    )
    return 0


def filter_projects(projects, args):
    filtered_projects = []
    for project in projects:
        project_slug = project[1]
        project_cwe_id = project[3]

        if args.cwe and not any(cwe == project_cwe_id for cwe in args.cwe):
            continue
        if args.filter and not any(f in project_slug for f in args.filter):
            continue
        if args.exclude and any(f in project_slug for f in args.exclude):
            continue
        filtered_projects.append(project)
    return filtered_projects


if __name__ == "__main__":
    sys.exit(main())
