import csv

def export_to_csv(response, headers, data):
    writer = csv.writer(response)
    writer.writerow(headers)

    for row in data:
        writer.writerow(row)

    return response