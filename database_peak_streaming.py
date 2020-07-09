import hyperion
import asyncio
import numpy
import time
import sqlite3
import csv
import os

instrument_ip = '10.0.0.55'
num_of_peaks = 8
num_of_ports = 8
streaming_time = 100 # Years long

async def get_data(con):
    repeat = time.time()
    big_port_numbers = []; big_peak_data = []
    while True:
        if time.time()-repeat < 10: # Every day/hour
            peak_num = []
            begin = time.time()
            while time.time()-begin < .097:
                peak_data = await queue.get()
                queue.task_done()
                if peak_data['data']:
                    peak_num.append(list(peak_data['data'].data))
                else:
                    return

            ts = time.time()

            sensors_num = []
            for port_list in peak_data['data'].channel_slices[:num_of_ports]:
                sensors_num.append(len(port_list))
            sensors_num.insert(0, ts)

            big_port_numbers.append(sensors_num)

            average_peak_num = []
            for peak in range(len(peak_num[0])):
                current_sensor = []
                for data_list in peak_num:
                    current_sensor.append(data_list[peak])
                average_peak_num.append(numpy.mean(current_sensor))

            big_peak_data.append(average_peak_num)

        else:
            repeat = time.time()
            add_data(con, big_port_numbers, big_peak_data)
            delete_data(repeat)
            big_port_numbers = []; big_peak_data = []
            export_csv(con)

def add_data(con, data, peak_data):
    with con:
        cur.executemany(peak_sql, peak_data)
        cur.executemany(data_sql, data)

def delete_data(current_time):
    with con:
        cur.execute('delete from data where '+str(current_time)+'-timestamp > 30')
        data_id = cur.execute('select id from data limit 1').fetchone()
        cur.execute('delete from peak_data where id < '+str(data_id[0]))

def export_csv(con):
    for table in database_tables:
        cur.execute('select * from '+table+';')
        with open('csv/'+table+'.csv', 'w', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([i[0] for i in cur.description])
            csv_writer.writerows(cur)

def create_table(con, create_table_sql):
    with con:
        cur.execute(create_table_sql)

peak_question = ','.join('?' * (num_of_peaks))
data_question = ','.join('?' * (num_of_ports+1))
peak_parameters = ','.join('peak'+str(i) for i in range(1,num_of_peaks+1))
data_parameters = ','.join('port'+str(i) for i in range(1,num_of_ports+1))
peak_table_variables = ','.join('peak'+str(i)+' float UNSIGNED' for i in range(1,num_of_peaks+1))
data_table_variables = ','.join('port'+str(i)+' smallint UNSIGNED' for i in range(1,num_of_ports+1))

create_peak_data_table = 'create table if not exists peak_data (id integer PRIMARY KEY,{});'.format(peak_table_variables)
create_data_table = 'create table if not exists data (id integer PRIMARY KEY,timestamp double NOT NULL,{});'.format(data_table_variables)

peak_sql = 'insert into peak_data({parameters}) VALUES({question})'.format(parameters = peak_parameters, question = peak_question)
data_sql = 'insert into data(timestamp,{parameters}) VALUES({question})'.format(parameters = data_parameters, question = data_question)

database_tables = ('peak_data','data')

for folder in ('database','csv'):
    os.makedirs('./'+folder, exist_ok = True)

con = sqlite3.connect('database/peak_data.db')
cur = con.cursor()

if con:
    create_table(con, create_peak_data_table)
    create_table(con, create_data_table)
else:
    raise Exception('Cannot create database connection.')

loop = asyncio.get_event_loop()
queue = asyncio.Queue(maxsize=5, loop=loop)
stream_active = True

peaks_streamer = hyperion.HCommTCPPeaksStreamer(instrument_ip, loop, queue)

loop.create_task(get_data(con))
loop.call_later(streaming_time, peaks_streamer.stop_streaming)
loop.run_until_complete(peaks_streamer.stream_data())