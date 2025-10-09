def map_course_payload(course_name: str, section: str | None, room: str | None, owner_email: str):
    return {
        "name": course_name,
        "section": section,
        "room": room,
        "ownerId": owner_email,
        "courseState": "ACTIVE",
    }