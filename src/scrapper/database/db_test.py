import db

def test_row_exists():
    # Test data
    test_date = "2025-10-04 12:00:00"
    test_label = "Test Crime"
    test_coordinates = [123.456, 78.910]
    test_trust = 2

    print("=== Starting row_exists tests ===")

    # Ensure the row does not exist yet
    assert not db.row_exists(test_date, test_label, test_coordinates), "Row should not exist yet"

    # Add the test row
    db.add_row(
        date=test_date,
        label=test_label,
        address="Test Address",
        city="Test City",
        coordinates=test_coordinates,
        trust=test_trust
    )

    # Check that row_exists returns True
    assert db.row_exists(test_date, test_label, test_coordinates), "Row should exist after insertion"
    print("✅ row_exists detected the inserted row correctly")

    # Check that a different row does not exist
    assert not db.row_exists(test_date, "Nonexistent Crime", test_coordinates), "Non-existent row should not exist"
    print("✅ row_exists correctly ignored a non-existent row")

    # Clean up: delete the inserted row
    rows = db.view_all()
    for row in rows:
        if row['date'] == test_date and row['label'] == test_label:
            db.delete_row(row['id'])

    # Ensure cleanup
    assert not db.row_exists(test_date, test_label, test_coordinates), "Row should be deleted"
    print("✅ Cleanup successful, row deleted")

    print("=== All tests passed ===")


if __name__ == "__main__":
    test_row_exists()