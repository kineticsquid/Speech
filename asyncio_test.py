import asyncio
from random import randint

async def a(results):
    for i in range(0, 5):
        results.append('A%s' % i)
        sleep = randint(0, 3)/5
        results.append('A sleeping for %ss' % sleep)
        await asyncio.sleep(sleep)
    return('Done A')

async def b(results):
    for i in range(0, 5):
        results.append('B%s' % i)
        sleep = randint(0, 3)/5
        results.append('B sleeping for %ss' % sleep)
        await asyncio.sleep(sleep)
    return('Done B')

def done():
    print('Done')

results = []
print('Starting A')
results_a = asyncio.run(a(results))
print('A results: %s' % results_a)
print('Ending A')
print('Starting B')
results_b = asyncio.run(b(results))
print('B results: %s' % results_b)
print('Ending B')

print('Results:')
print(results)

print('starting event loop')
results = []
try:
    event_loop = asyncio.get_event_loop()
except RuntimeError:
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
a = event_loop.create_task(a(results))
b = event_loop.create_task(b(results))

event_loop.run_until_complete(a)
event_loop.run_until_complete(b)
event_loop.close()

print('ending event loop')

print('Results:')
print(results)

