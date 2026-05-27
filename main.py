import os
import uvicorn
from fastapi import FastAPI
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

app = FastAPI()

class Rental(BaseModel):
    inventory_id: int
    customer_id: int
    staff_id: int

class Payment(BaseModel):
    customer_id: int
    staff_id: int
    rental_id: int
    amount: float

@app.get("/")
def inicio():
    return {"status": "Servidor Sakila en la Nube Operativo"}

# VER INVENTARIO COMPLETO CON NOMBRES DE PELÍCULAS
@app.get("/inventory")
def listar_inventario():
    # Hacemos un join con la tabla film para traer el título
    query = supabase.table("inventory").select("inventory_id, available, film(title, rental_rate)").execute()
    return query.data

# GUI 05: REGISTRAR UN NUEVO ALQUILER
@app.post("/rentals")
def crear_alquiler(rental: Rental):
    # Validar inventario y traer el título de la película
    inventario = supabase.table("inventory").select("inventory_id, available, film(title)").eq("inventory_id", rental.inventory_id).execute()
    if not inventario.data:
        return {"error": "El ID de inventario no existe"}
    
    inv_data = inventario.data[0]
    if inv_data["available"] == False:
        return {"error": f"La película '{inv_data['film']['title']}' NO está disponible"}

    # Validar que el cliente exista
    cliente = supabase.table("customer").select("first_name, last_name").eq("customer_id", rental.customer_id).execute()
    if not cliente.data:
        return {"error": "El cliente no está registrado"}

    # Registrar alquiler
    nuevo = supabase.table("rental").insert({
        "inventory_id": rental.inventory_id,
        "customer_id": rental.customer_id,
        "staff_id": rental.staff_id
    }).execute()

    # Cambiar estado a no disponible
    supabase.table("inventory").update({"available": False}).eq("inventory_id", rental.inventory_id).execute()

    return {
        "mensaje": "Alquiler procesado exitosamente",
        "pelicula": inv_data["film"]["title"],
        "cliente": f"{cliente.data[0]['first_name']} {cliente.data[0]['last_name']}"
    }

# GUI 05: PROCESAR UNA DEVOLUCIÓN
@app.put("/returns/{rental_id}")
def devolver_pelicula(rental_id: int):
    rental = supabase.table("rental").select("inventory_id, inventory(film(title))").eq("rental_id", rental_id).execute()
    if not rental.data:
        return {"error": "ID de alquiler no encontrado"}
    
    inv_id = rental.data[0]["inventory_id"]
    titulo_pelicula = rental.data[0]["inventory"]["film"]["title"]

    # Actualizar fechas y liberar inventario
    supabase.table("rental").update({"return_date": "now()"}).eq("rental_id", rental_id).execute()
    supabase.table("inventory").update({"available": True}).eq("inventory_id", inv_id).execute()

    return {"mensaje": f"La película '{titulo_pelicula}' ha sido devuelta y liberada en el inventario"}

# GUI 06: MÓDULO DE CAJA (REGISTRAR PAGO)
@app.post("/payments")
def crear_pago(payment: Payment):
    # Validar cliente
    cliente = supabase.table("customer").select("first_name, last_name").eq("customer_id", payment.customer_id).execute()
    if not cliente.data:
        return {"error": "Cliente no existe"}

    # Registrar el pago
    nuevo_pago = supabase.table("payment").insert({
        "customer_id": payment.customer_id,
        "staff_id": payment.staff_id,
        "rental_id": payment.rental_id,
        "amount": payment.amount
    }).execute()

    return {
        "mensaje": "Pago registrado en caja",
        "cliente": f"{cliente.data[0]['first_name']} {cliente.data[0]['last_name']}",
        "monto_cobrado": payment.amount
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)