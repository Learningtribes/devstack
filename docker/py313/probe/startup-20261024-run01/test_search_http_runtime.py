"""Exercise the real LMS course-search route against the local index."""
import django
from django.contrib.auth import get_user_model
from django.test import Client

django.setup()


def main():
    client = Client()
    user = get_user_model().objects.get(username="edx")
    client.force_login(user)
    response = client.get("/api/courses/v1/courses/?search_term=Python", HTTP_HOST="localhost:18000")
    print("status", response.status_code)
    if response.status_code != 200:
        print(response.content[:300].decode("utf-8", "replace"))
        raise AssertionError("course search route did not return 200")
    payload = response.json()
    print("payload_keys", sorted(payload))
    print("course_ids", [item.get("course_id") for item in payload.get("results", [])])


if __name__ == "__main__":
    main()
