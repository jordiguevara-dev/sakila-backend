import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

app = FastAPI()

# Buenas Prácticas: Habilitar CORS por si luego conectas un frontend Web (React/Angular)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic actualizados
class Rental(BaseModel):
    inventory_id: int
    customer_id: int
    staff_id: int

class Payment(BaseModel):
    inventory_id: int  # <-- CAMBIO CLAVE: Usamos inventory_id en lugar de rental_id
    amount: float

class CustomerInput(BaseModel):
    store_id: int
    first_name: str
    last_name: str
    email: str

@app.get("/")
def inicio():
    return {"status": "Servidor Sakila en la Nube Operativo"}

@app.get("/inventory")
def listar_inventario():
    # Ordenado por ID para que la tabla en Java no salte de orden al actualizarse
    query = supabase.table("inventory").select("inventory_id, available, store_id, film(title, rental_rate)").order("inventory_id").execute()
    
    lista_plana = []
    for item in query.data:
        lista_plana.append({
            "inventory_id": str(item["inventory_id"]),
            "available": str(item["available"]).lower(),
            "store_id": str(item["store_id"]),
            "title": str(item["film"]["title"]).upper() if item["film"] else "PELÍCULA DESCONOCIDA",
            "rental_rate": str(item["film"]["rental_rate"]) if item["film"] else "2.99"
        })
    return lista_plana

@app.get("/customers")
def listar_clientes():
    query = supabase.table("customer").select("customer_id, first_name, last_name, email, active").order("customer_id").execute()
    lista_clientes = []
    for c in query.data:
        lista_clientes.append({
            "customer_id": str(c["customer_id"]),
            "first_name": str(c["first_name"]),
            "last_name": str(c["last_name"]),
            "email": str(c["email"]),
            "active": str(c["active"]).lower()
        })
    return lista_clientes

@app.post("/rentals")
def crear_alquiler(rental: Rental):
    inventario = supabase.table("inventory").select("inventory_id, available").eq("inventory_id", rental.inventory_id).execute()
    if not inventario.data or not inventario.data[0]["available"]:
        return {"error": "La película NO está disponible o no existe"}

    supabase.table("rental").insert({
        "inventory_id": rental.inventory_id,
        "customer_id": rental.customer_id,
        "staff_id": rental.staff_id
    }).execute()

    supabase.table("inventory").update({"available": False}).eq("inventory_id", rental.inventory_id).execute()
    return {"status": "success"}

# CAMBIO CLAVE: Ahora recibe inventory_id
@app.put("/returns/{inventory_id}")
def devolver_pelicula(inventory_id: int):
    # 1. Reestablecer stock físico
    supabase.table("inventory").update({"available": True}).eq("inventory_id", inventory_id).execute()
    
    # 2. Buscar el alquiler activo (el que aún no tiene fecha de retorno) y cerrarlo
    rentals = supabase.table("rental").select("rental_id").eq("inventory_id", inventory_id).is_("return_date", "null").execute()
    
    if rentals.data:
        r_id = rentals.data[0]["rental_id"]
        fecha_actual = datetime.utcnow().isoformat()
        supabase.table("rental").update({"return_date": fecha_actual}).eq("rental_id", r_id).execute()
    
    return {"status": "success"}

@app.post("/payments")
def crear_pago(payment: Payment):
    # Buscar el alquiler más reciente asociado a este inventario
    rentals = supabase.table("rental").select("rental_id, customer_id, staff_id").eq("inventory_id", payment.inventory_id).order("rental_date", desc=True).limit(1).execute()
    
    if not rentals.data:
        return {"error": "No hay alquileres registrados para este inventario"}
    
    r_data = rentals.data[0]

    supabase.table("payment").insert({
        "customer_id": r_data["customer_id"],
        "staff_id": r_data["staff_id"],
        "rental_id": r_data["rental_id"],
        "amount": payment.amount
    }).execute()

    return {"status": "success"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)