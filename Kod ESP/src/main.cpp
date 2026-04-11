#include <Arduino.h>
#include <ESP32Servo.h>
#include <vector>
#include <map>

const int pinSerwoPoziom = 18;
const int pinSerwoPion = 23;
const int wlaczLidar = 19;
const int rx = 16;
const int tx = 17;

Servo serwoPoziom;
Servo serwoPion;

int currentAngle = 90;
int odleglosc = 0;
int silaSygnalu = 0;
static int aktualnyKatPoziom = 0;
static int aktualnyKatPion = 0;

int skokKataPion = 5;
int skokKataPoziom = 5;
int kierunek = 1;
int kierunekPion = 1;
unsigned long ostatniRuch = 0;
static int predkoscRuchu = 20;

bool stanSkanWlaczony = false;
bool stanOdczytLidar = false;
bool stanPelnySkan = false;


std::map<String, String> listaKomend = {
  {"m1", "Wybor serwa : kat"},
  {"m2", "Wybor serwa : kat"},
  {"predkosc","Ustawia opoznienie kroku po : "},
  {"skokpion","Ustawia skok w pionie po : "},
  {"skokpoziom","Ustawia skok w poziomie po : "},
  {"odleglosc","Jednorazowy pomiar odleglosci"},
  {"skan","Skan w jednej plaszczyznie"},
  {"pelnyskan", "Uruchamia pelny skan"},
  {"stop", "Zatrzymuje wszystkie czynnosci"},
  {"zero", "Zeruje pozycje lasera"},
  {"pomiar", "Uruchamia ciagly pomiar odleglosci"},
  {"zakoncz", "Zakancza ciagly pomiar odleglosci"},
  {"status", "Wyswietla status pamieci RAM i FLASH systemu"},
  {"help", "Podaje liste dostepnych komend"},
};

int odczytChwilowy() {
  while (Serial2.available()) Serial2.read();
  unsigned long start = millis();
  while (Serial2.available() < 9) {
    if (millis() - start > 50) return -1;
  }
  while (Serial2.available() >= 9) {
    if (Serial2.read() == 0x59) {
      if (Serial2.peek() == 0x59) {
        Serial2.read();
        uint8_t low = Serial2.read();
        uint8_t high = Serial2.read();
        for (int i = 0; i < 5; i++) Serial2.read();
        return low + (high << 8);
      }
    }
  }
  return -1;
}
bool odczytajLidar() {
  if (Serial2.available() >= 9) {
    if (Serial2.read() == 0x59) {
      if (Serial2.read() == 0x59) {
        uint8_t buffer[7];
        Serial2.readBytes(buffer, 7);
        uint8_t checksum = 0x59 + 0x59;
        for (int i = 0; i < 6; i++) {
          checksum += buffer[i];
        }
        if (checksum == buffer[6]) {
          odleglosc = buffer[0] + (buffer[1] << 8);
          silaSygnalu = buffer[2] + (buffer[3] << 8);
          return true;
        }
      }
    }
  }
  return false;
}
void sprawdzRAM() {
  uint32_t wolny = ESP.getFreeHeap();
  uint32_t calosc = ESP.getHeapSize();
  uint32_t zajety = calosc - wolny;
  float procent = ((float)zajety / calosc) * 100.0;
  Serial.print("----------------------------------\n");
  Serial.printf("RAM: %u / %u (%.2f%%)\n", zajety, calosc, procent);
}
void sprawdzFlash() {
  uint32_t rozmiarProgramu = ESP.getSketchSize();
  uint32_t dostepnaPamiec = ESP.getFlashChipSize();
  float procent = ((float)rozmiarProgramu / dostepnaPamiec) * 100.0;
  Serial.printf("FLASH: %u / %u (%.2f%%)\n", rozmiarProgramu,dostepnaPamiec, procent);
  Serial.print("----------------------------------\n");
}
void ruchSerwaPionu(int kat) {
  int impuls = map(kat+20, 0, 145, 750, 2250);
  aktualnyKatPion = kat;
  serwoPion.writeMicroseconds(impuls);

}
void ruchSerwaPoziomu(int kat) {
  int impuls = map(kat, 0, 180, 500, 2500);
  aktualnyKatPoziom = kat;
  serwoPoziom.writeMicroseconds(impuls);
}
void skanowanie() {
  if (millis() - ostatniRuch >= predkoscRuchu) {
    ostatniRuch = millis();
    aktualnyKatPoziom += kierunek;
    if (aktualnyKatPoziom >= 180) {
      aktualnyKatPoziom = 180;
      kierunek = -1;
    }
    else if (aktualnyKatPoziom <= 0) {
      aktualnyKatPoziom = 0;
      kierunek = 1;
    }
    ruchSerwaPoziomu(aktualnyKatPoziom);

    int d = odczytChwilowy();
    Serial.print("Pion:");
    Serial.print(aktualnyKatPion);
    Serial.print(" | Poz:");
    Serial.print(aktualnyKatPoziom);
    Serial.print(" | Dist:");
    Serial.print(d);
    Serial.print("\n");
  }
}
void PelnySkan() {
  if (millis() - ostatniRuch >= predkoscRuchu) {
    ostatniRuch = millis();
    aktualnyKatPoziom += kierunek;
    if (aktualnyKatPoziom > 180 || aktualnyKatPoziom < 0) {
      aktualnyKatPoziom = (aktualnyKatPoziom > 180) ? 180 : 0;
      kierunek *= -1;
      aktualnyKatPion += skokKataPion*kierunekPion;
      if (aktualnyKatPion >= 90) {
        aktualnyKatPion = 90;
        kierunekPion = -1;
      }
      if (aktualnyKatPion <= 0) {
        aktualnyKatPion = 0;
        kierunekPion = 1;
      }
      ruchSerwaPionu(aktualnyKatPion);
    }
    ruchSerwaPoziomu(aktualnyKatPoziom);
    int d = odczytChwilowy();
    Serial.print("Pion:");
    Serial.print(aktualnyKatPion);
    Serial.print(" | Poz:");
    Serial.print(aktualnyKatPoziom);
    Serial.print(" | Dist:");
    Serial.print(d);
    Serial.print("\n");
  }
}
void zerowanie() {
  aktualnyKatPoziom = 90;
  aktualnyKatPion = 0;
  ruchSerwaPionu(aktualnyKatPion);
  ruchSerwaPoziomu(aktualnyKatPoziom);
}
void obslugaKomend() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    int separatorIndex = input.indexOf(':');
    if (separatorIndex != -1) {
      String motor = input.substring(0, separatorIndex);
      int angle = input.substring(separatorIndex + 1).toInt();
      if (motor == "M1" || motor == "m1") {
        ruchSerwaPionu(angle);
        Serial.print("Serwo M1 przesuniete na kat: ");
        Serial.println(angle);
      }
      else if (motor == "M2" || motor == "m2") {
        ruchSerwaPoziomu(angle);
        Serial.print("Serwo M2 przesuniete na kat: ");
        Serial.println(angle);
      }
      else if (motor == "predkosc" || motor == "PREDKOSC") {
        predkoscRuchu = angle;
        Serial.print("Ustawiono predkosc ruchu na: ");
        Serial.println(predkoscRuchu);
      }
      else if (motor == "skokpion" || motor == "SKOKPION") {
        skokKataPion = angle;
        Serial.print("Ustawiono skok Pion na: ");
        Serial.println(skokKataPion);
      }
      else if (motor == "skokpoziom" || motor == "SKOKPOZIOM") {
        skokKataPoziom = angle;
        Serial.print("Ustawiono skok Poziom na: ");
        Serial.println(skokKataPoziom);
      }
    }
    else if (input == "odleglosc" || input == "ODLEGLOSC") {
      int chwilowaOdleglosc = odczytChwilowy();
      Serial.printf("Odleglosc wynosi: %d", chwilowaOdleglosc);
      Serial.print("\n");
    }
    else if (input == "skan" || input == "SKAN") {
      stanSkanWlaczony = true;
      Serial.print("Rozpoczeto skan");
      Serial.print("\n");
    }
    else if (input == "pelnyskan" || input == "PELNYSKAN") {
      zerowanie();
      stanPelnySkan = true;
      Serial.print("Rozpoczeto pelny skan");
      Serial.print("\n");
    }
    else if (input == "stop" || input == "STOP") {
      stanSkanWlaczony = false;
      stanPelnySkan = false;
      Serial.print("Zatrzymano skan");
      Serial.print("\n");
    }
    else if (input == "zero" || input == "ZERO") {
      zerowanie();
    }
    else if (input == "pomiar" || input == "POMIAR") {
      stanOdczytLidar = true;
      Serial.print("Rozpoczeto odczyt");
      Serial.print("\n");
    }
    else if (input == "zakoncz" || input == "ZAKONCZ") {
      stanOdczytLidar = false;
      Serial.print("Zakonczono odczyt ");
      Serial.print("\n");
    }
    else if (input == "status" || input == "STATUS") {
      sprawdzRAM();
      sprawdzFlash();
    }
    else if (input == "help" || input == "HELP") {
      Serial.println("\nDostepne komendy");
      for (auto const& [komenda, opis] : listaKomend) {
        Serial.print(" > ");
        Serial.print(komenda);
        int spaces = 15 - komenda.length();
        for (int i = 0; i < spaces; i++) Serial.print(" ");
        Serial.print("- ");
        Serial.println(opis);
      }
    }
    else {
      Serial.print("Podano niepoprawna komende: ");
      Serial.println(input);
      Serial.print("\n");
    }
  }
}

void setup() {

  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, rx, tx);
  Serial.println("Interfejs szeregowy zainicjalizowany!");
  Serial.println("Inicjalizuje dalmierz...");
  pinMode(wlaczLidar, OUTPUT);
  digitalWrite(wlaczLidar, HIGH);
  Serial.println("Dalmierz zainicjalizowany!");
  Serial.println("Inicjalizuje serwa...");
  serwoPoziom.attach(pinSerwoPoziom, 500, 2500);
  serwoPion.attach(pinSerwoPion, 750, 2250);
  Serial.println("Serwa zainicjowane!");
  Serial.println("Zeruje pozycje dalmierza...");
  zerowanie();
  Serial.println("Pozycja wyzerowana!");
  Serial.println("SYSTEM GOTOWY\n");
}

void loop() {
  obslugaKomend();
  if (stanSkanWlaczony == true) {
    skanowanie();
  }
  if (stanPelnySkan == true) {
    PelnySkan();
  }
  if (stanOdczytLidar == true) {
    odczytajLidar();
    Serial.print("Pion:");
    Serial.print(aktualnyKatPion);
    Serial.print(" | Poz:");
    Serial.print(aktualnyKatPoziom);
    Serial.print(" | Dist:");
    Serial.print(odleglosc);
    Serial.print("\n");
  }
}
