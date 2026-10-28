from flask import Flask, request, render_template
from flask import Flask, request, render_template
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import os
from config import connect

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("static/charts", exist_ok=True)


def create_charts(monthly):

    months = monthly.index

    plt.figure(figsize=(8, 5))
    plt.plot(
        months,
        monthly["average_temperature"],
        marker="o"
    )
    plt.title("Monthly Average Temperature")
    plt.xlabel("Month")
    plt.ylabel("Temperature (°C)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("static/charts/temperature.png")
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(
        months,
        monthly["average_humidity"],
        marker="o"
    )
    plt.title("Monthly Average Humidity")
    plt.xlabel("Month")
    plt.ylabel("Humidity (%)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("static/charts/humidity.png")
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.bar(
        months,
        monthly["total_rainfall"]
    )
    plt.title("Monthly Total Rainfall")
    plt.xlabel("Month")
    plt.ylabel("Rainfall (mm)")
    plt.tight_layout()
    plt.savefig("static/charts/rainfall.png")
    plt.close()


@app.route("/")
def home():
    return render_template("dashboard.html")


@app.route("/upload", methods=["POST"])
def upload():

    files = request.files.getlist("files")

    if not files or all(file.filename == "" for file in files):
        return "No files selected"

    total_rows = 0
    total_valid = 0
    total_invalid = 0
    total_missing = 0
    total_duplicates = 0

    missing_by_column = {}
    uploaded_files = []

    try:

        connection = connect()
        cursor = connection.cursor()

        check_query = """
        SELECT COUNT(*)
        FROM weather_records
        WHERE observation_date = %s
        AND location = %s
        AND temperature = %s
        AND humidity = %s
        AND rainfall = %s
        """

        insert_query = """
        INSERT IGNORE INTO weather_records
        (observation_date, location, temperature, humidity, rainfall)
        VALUES (%s, %s, %s, %s, %s)
        """

        for file in files:

            if file.filename == "":
                continue

            if not file.filename.lower().endswith(".csv"):
                continue

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                file.filename
            )

            file.save(filepath)

            try:
                data = pd.read_csv(filepath)
            except Exception:
                continue

            required_columns = [
                "observation_date",
                "location",
                "temperature",
                "humidity",
                "rainfall"
            ]

            missing_columns = [
                column
                for column in required_columns
                if column not in data.columns
            ]

            if missing_columns:
                continue

            data["observation_date"] = pd.to_datetime(
                data["observation_date"],
                errors="coerce"
            )

            data["temperature"] = pd.to_numeric(
                data["temperature"],
                errors="coerce"
            )

            data["humidity"] = pd.to_numeric(
                data["humidity"],
                errors="coerce"
            )

            data["rainfall"] = pd.to_numeric(
                data["rainfall"],
                errors="coerce"
            )

            invalid = (
                data["observation_date"].isna()
                | data["location"].isna()
                | (data["location"].astype(str).str.strip() == "")
                | data["temperature"].isna()
                | data["humidity"].isna()
                | data["rainfall"].isna()
                | (data["humidity"] < 0)
                | (data["humidity"] > 100)
                | (data["rainfall"] < 0)
            )

            valid_data = data[~invalid]

            total_rows += len(data)
            total_invalid += int(invalid.sum())
            total_missing += int(data.isnull().sum().sum())

            for column, count in data.isnull().sum().items():

                if column not in missing_by_column:
                    missing_by_column[column] = 0

                missing_by_column[column] += int(count)

            for _, row in valid_data.iterrows():

                values = (
                    row["observation_date"].date(),
                    row["location"],
                    row["temperature"],
                    row["humidity"],
                    row["rainfall"]
                )

                cursor.execute(check_query, values)

                exists = cursor.fetchone()[0]

                if exists > 0:
                    total_duplicates += 1
                else:
                    cursor.execute(insert_query, values)
                    total_valid += 1

            uploaded_files.append(file.filename)

        connection.commit()

        cursor.close()
        connection.close()

    except Exception:
        return render_template(
            "error.html",
            message="Unable to process the uploaded files."
        )

    if total_rows == 0:
        return render_template(
            "error.html",
            message="No valid CSV files were uploaded."
        )

    return render_template(
        "upload_result.html",
        valid_count=total_valid,
        invalid_count=total_invalid,
        missing_count=total_missing,
        duplicate_count=total_duplicates,
        total_rows=total_rows,
        missing_by_column=missing_by_column,
        uploaded_files=uploaded_files
    )
@app.route("/analysis")
def analysis():

    try:
        connection = connect()

        query = """
        SELECT observation_date, location, temperature, humidity, rainfall
        FROM weather_records
        """

        data = pd.read_sql(query, connection)

        connection.close()

    except Exception:
        return render_template(
            "error.html",
            message="Unable to retrieve weather data from the database."
        )

    if len(data) == 0:
        return render_template(
            "error.html",
            message="No weather records are available for analysis."
        )

    total_records = len(data)

    average_temperature = round(
        data["temperature"].mean(),
        2
    )

    average_humidity = round(
        data["humidity"].mean(),
        2
    )

    total_rainfall = round(
        data["rainfall"].sum(),
        2
    )

    highest_temperature = round(
        data["temperature"].max(),
        2
    )

    data["observation_date"] = pd.to_datetime(
        data["observation_date"]
    )

    data["month"] = data["observation_date"].dt.month

    monthly = data.groupby("month").agg(
        average_temperature=("temperature", "mean"),
        maximum_temperature=("temperature", "max"),
        minimum_temperature=("temperature", "min"),
        average_humidity=("humidity", "mean"),
        total_rainfall=("rainfall", "sum")
    )

    monthly = monthly.round(2)

    monthly.index = monthly.index.map({
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December"
    })

    print("\nMONTHLY WEATHER ANALYSIS")
    print(monthly)

    create_charts(monthly)

    monthly = monthly.reset_index()

    return render_template(
        "analysis.html",
        total_records=total_records,
        average_temperature=average_temperature,
        average_humidity=average_humidity,
        total_rainfall=total_rainfall,
        highest_temperature=highest_temperature,
        monthly=monthly.reset_index().to_dict("records")
    )
@app.route("/city-comparison")
def city_comparison():

    try:
        connection = connect()

        query = """
        SELECT
            location,
            AVG(temperature) AS average_temperature,
            AVG(humidity) AS average_humidity,
            SUM(rainfall) AS total_rainfall,
            MAX(temperature) AS highest_temperature
        FROM weather_records
        GROUP BY location
        ORDER BY location
        """

        data = pd.read_sql(query, connection)

        connection.close()

    except Exception:
        return render_template(
            "error.html",
            message="Unable to retrieve city comparison data."
        )

    if len(data) == 0:
        return render_template(
            "error.html",
            message="No weather data is available for comparison."
        )

    data = data.round(2)

    cities = data["location"].tolist()

    plt.figure(figsize=(8, 5))
    plt.bar(cities, data["average_temperature"])
    plt.title("Average Temperature by City")
    plt.xlabel("City")
    plt.ylabel("Temperature (°C)")
    plt.tight_layout()
    plt.savefig("static/charts/city_temperature.png")
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.bar(cities, data["average_humidity"])
    plt.title("Average Humidity by City")
    plt.xlabel("City")
    plt.ylabel("Humidity (%)")
    plt.tight_layout()
    plt.savefig("static/charts/city_humidity.png")
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.bar(cities, data["total_rainfall"])
    plt.title("Total Rainfall by City")
    plt.xlabel("City")
    plt.ylabel("Rainfall (mm)")
    plt.tight_layout()
    plt.savefig("static/charts/city_rainfall.png")
    plt.close()

    return render_template(
        "city_comparison.html",
        cities=data.to_dict("records")
    )



if __name__ == "__main__":
    app.run(debug=True)
    app = Flask(__name__)