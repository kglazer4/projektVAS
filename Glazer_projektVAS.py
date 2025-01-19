from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import random
import asyncio

class Particle:
    def __init__(self):
        self.position = random.randint(10, 60)  
        self.velocity = random.uniform(-1, 1)   
        self.best_position = self.position      
        self.best_fitness = float('inf')       

    def evaluate(self, queue_length):
        green_duration = int(self.position)  

        max_duration = 60  
        if green_duration > max_duration:
            penalty = (green_duration - max_duration) * 1 
        else:
            penalty = 0

        fitness = abs(queue_length - green_duration) + penalty
        
        if fitness < self.best_fitness:
            self.best_fitness = fitness
            self.best_position = self.position

        return fitness

async def pso_for_green_light_duration(queue_length):
    num_particles = 5
    particles = [Particle() for _ in range(num_particles)]

    max_iterations = 20
    inertia_weight = 0.5
    cognitive_weight = 1.5
    social_weight = 1.5

    for _ in range(max_iterations):
        for particle in particles:
            fitness = particle.evaluate(queue_length)

            particle.velocity = (inertia_weight * particle.velocity +
                                 cognitive_weight * random.random() * (particle.best_position - particle.position) +
                                 social_weight * random.random() * (particle.best_position - particle.position))
            
            particle.position += particle.velocity
            particle.position = max(min(particle.position, 60), 10) 

    best_particle = min(particles, key=lambda p: p.best_fitness)
    return int(best_particle.best_position)

async def countdown(seconds, label, queue_length):
    for i in range(seconds, 0, -1):
        if queue_length > 0:
            cars_departing = random.choice([0, 1])
        else:
            cars_departing = 0

        queue_length -= cars_departing
        queue_length = max(queue_length, 0)

        print(f"[{label}] Green light ends in {i} seconds... {cars_departing} cars departed, {queue_length} cars left in queue.")

        await asyncio.sleep(1)

    return queue_length

class NorthSouthAgent(Agent):
    class ManageTrafficBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()
            self.queue_length = 0  

        async def run(self):
            cars_arriving = random.randint(0, 20)
            self.queue_length += cars_arriving
            print(f"[NorthSouth] {cars_arriving} cars arrived. Queue length: {self.queue_length}.")

            green_duration = await pso_for_green_light_duration(self.queue_length) 

            self.queue_length = await countdown(green_duration, "NorthSouth", self.queue_length) 

            msg = Message(to="horizontal@localhost") 
            msg.body = "Your turn"
            await self.send(msg)

            print("[NorthSouth] Red light, waiting for EastWest to finish.")

            response = await self.receive(timeout=65) 
            if response:
                print("[NorthSouth] Received message: Start green light.")
            else:
                print("[NorthSouth] Timeout waiting for EastWest.")

    async def setup(self):
        print("NorthSouthAgent starting...")
        b = self.ManageTrafficBehaviour()
        self.add_behaviour(b)

class EastWestAgent(Agent):
    class ManageTrafficBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()
            self.queue_length = 0 

        async def run(self):
            msg = await self.receive(timeout=65)
            if msg:
                print("[EastWest] Received message: Start green light.")

                cars_arriving = random.randint(0, 40)
                self.queue_length += cars_arriving
                print(f"[EastWest] {cars_arriving} cars arrived. Queue length: {self.queue_length}.")

                green_duration = await pso_for_green_light_duration(self.queue_length)  

                self.queue_length = await countdown(green_duration, "EastWest", self.queue_length)

                response = Message(to="vertical@localhost") 
                response.body = "Your turn"
                await self.send(response)

                print("[EastWest] Red light, waiting for NorthSouth to finish.")
            else:
                print("[EastWest] Timeout waiting for NorthSouth.")

    async def setup(self):
        print("EastWestAgent starting...")
        b = self.ManageTrafficBehaviour()
        self.add_behaviour(b)

if __name__ == "__main__":
    north_south_jid = "vertical@localhost" 
    north_south_password = "vertical" 

    east_west_jid = "horizontal@localhost"  
    east_west_password = "horizontal" 

    north_south_agent = NorthSouthAgent(north_south_jid, north_south_password)
    east_west_agent = EastWestAgent(east_west_jid, east_west_password)

    future_north_south = north_south_agent.start()
    future_east_west = east_west_agent.start()

    asyncio.get_event_loop().run_until_complete(asyncio.gather(future_north_south, future_east_west))

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("Stopping agents...")
        asyncio.get_event_loop().run_until_complete(north_south_agent.stop())
        asyncio.get_event_loop().run_until_complete(east_west_agent.stop())
