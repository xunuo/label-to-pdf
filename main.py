from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def scrape_doctors(url, doctor_type):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    doctors = []
    # We don't need days_of_week here since it's not used in this function

    for doctor_div in soup.find_all("div", class_="card"):
        img_tag = doctor_div.find("img")
        image = img_tag["src"] if img_tag else "Image tidak tersedia"
        name_tag = doctor_div.find("h6")
        name = name_tag.text.strip() if name_tag else "Nama tidak tersedia"

        schedule_table = doctor_div.find_next("table")
        schedule = []

        if schedule_table:
            for row in schedule_table.find_all("tr")[1:]:
                day = row.find("th").text.strip()
                time = row.find_all("td")
                times = [td.text.strip() for td in time if td.text.strip() != "- - -"]  # Menghindari jadwal kosong
                if times:  # Tambahkan hanya jika ada jam yang tersedia
                    schedule.append(f"{day}: {', '.join(times)}")

        # Menggabungkan jadwal menjadi string tunggal hanya jika ada jadwal yang valid
        schedule_str = "\n".join(schedule) if schedule else "Jadwal tidak tersedia"

        doctors.append({
            "image": image,
            "name": name,
            "schedule": schedule_str,
            "type": doctor_type  # Include the doctor type
        })

    return doctors

@app.route('/doctors', methods=['GET'])
def get_all_doctors():
    urls = [
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiQU5BIn0.4mn-CHZtv1Ger_2L_jonfDcnADP8Va4GzfQ_NNeZwVU",
            "type": "Dokter Spesialis Anak"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiQU5UIn0.q_Rg12NeKiR3tcSw2Qd-3beL2ttm5dsiLNFJxOzBA5k",
            "type": "Dokter Spesialis Anastesi"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiQkVEIn0.ohdLEPnqtGCsd0atK_F5jWfz1sqnRO8G1FSCykkHvlU",
            "type": "Dokter Spesialis Bedah"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiR0lHIn0._fQGxUAOsuys5Iu_xZJuuPQtKS2zr6I1WBFOhyyJkiw",
            "type": "Dokter Spesialis Gigi dan Mulut"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiSU5UIn0.KwMKBvDub6dV5jHrGj_WaBZ8D22Ny2otsKNIs4a7hiY",
            "type": "Dokter Spesialis Penyakit Dalam"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiS0xUIn0.qvPnfHw0h5CEQ2izgUOrKgisREcH1wlB1SE0KC6vChg",
            "type": "Dokter Spesialis Kulit dan Kelamin"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiTUFUIn0.yckN3KwDN9abT6gstg9lI8Z4P5PoiVuoz5dQz5D4UVE",
            "type": "Dokter Spesialis Mata"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiT0JHIn0.knHD2ybbhDNXG5vkciQcRYVkCJknDByUSKlm0iQXdIw",
            "type": "Dokter Spesialis Kandungan"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiUEFLIn0.TaSkLk2QTXMOPfmFCKvjsAoqyUhISZrc-pgAnrVmyLA",
            "type": "Dokter Spesialis Patologi Klinik"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiUEFSIn0.3UtGzb_b9XBDQB5UCbc-w8YEkZ86_a-t7f_myKw8uMg",
            "type": "Dokter Spesialis Paru"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiUkRPIn0.fAu37NlT_AD2hmqn4dRY9ENg5UqVqE3BOZlp1RHgkto",
            "type": "Dokter Spesialis Radiologi"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiU0FSIn0.SgiVnpAcTSvBnLURNES9kbpEOCSLBzRR7-cN_vScbm8",
            "type": "Dokter Spesialis Saraf"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiVEhUIn0.DzQOKuOe9IjRS3a-NrwU200vW9_k1TFJcwPSXuE5t5w",
            "type": "Dokter Spesialis THT-KL"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiMTAxIn0.VncL-YgcepzuzZal-zEusOZvaq5r89TdLJWi3q7Xhus",
            "type": "Dokter Spesialis Psikologi"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiMTcwNzQ0NDMxMCJ9.JShbr-XctB8NoCjokSBs6iDEEou_kuW0EGT3xwr3X5g",
            "type": "Dokter Spesialis Konservasi Gigi"
        },
        {
            "url": "https://rsaqidah.com/dokter/dokter-spesialis/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJrb2RlIjoiMTcxNDk3Mjg5MiJ9.Ig6c5B4cXqRHivDA8zHUoa4XTVJHEhgHAK5J5UasThg",
            "type": "Dokter Spesialis Kedokteran Jiwa"
        },
    ]

    all_doctors = []
    doctor_id_counter = 1  # Initialize a counter for unique doctor IDs

    # Collect doctors from both URLs
    for entry in urls:
        doctors = scrape_doctors(entry["url"], entry["type"])
        for doctor in doctors:
            doctor["id"] = doctor_id_counter  # Assign a unique ID to each doctor
            all_doctors.append(doctor)  # Combine all doctor data
            doctor_id_counter += 1  # Increment the ID for the next doctor

    return jsonify({
        "error": False,
        "message": "Success",
        "jadwaldoctors": all_doctors  # Return all doctors in one response
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
