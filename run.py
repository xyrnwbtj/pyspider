#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Binux<i@binux.me>
#         http://binux.me
# Created on 2014-03-05 00:11:49
#deneme 13 123123

import os
import sys
import time
import logging
import logging.config
logging.config.fileConfig("logging.conf")

from pyspider.database import connect_database
from pyspider.libs.utils import run_in_thread, run_in_subprocess

class Get(object):
    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        return self.getter()

# config form environment -------------------
class g(object):
    scheduler_xmlrpc_port = int(os.environ.get('SCHEDULER_XMLRPC_PORT', 23333))
    fetcher_xmlrpc_port = int(os.environ.get('FETCHER_XMLRPC_PORT', 24444))
    phantomjs_proxy_port = int(os.environ.get('PHANTOMJS_PROXY_PORT', 25555))
    webui_host = os.environ.get('WEBUI_HOST', '0.0.0.0')
    webui_port = int(os.environ.get('WEBUI_PORT', 5000))
    debug = bool(os.environ.get('DEBUG', False))
    queue_maxsize = int(os.environ.get('QUEUE_MAXSIZE', 100))
    demo_mode = bool(os.environ.get('DEMO_MODE'))

    # databases
    taskdb = None
    projectdb = None
    resultdb = None
    if os.environ.get('TASKDB'):
        if os.environ.get('TASKDB'):
            taskdb = Get(lambda : connect_database(os.environ['TASKDB']))
        if os.environ.get('PROJECTDB'):
            projectdb = Get(lambda : connect_database(os.environ['PROJECTDB']))
        if os.environ.get('RESULTDB'):
            resultdb = Get(lambda : connect_database(os.environ['RESULTDB']))
    elif os.environ.get('MYSQL_NAME'):
        taskdb = Get(lambda : connect_database(
                'mysql+taskdb://%(MYSQL_PORT_3306_TCP_ADDR)s'
                ':%(MYSQL_PORT_3306_TCP_PORT)s/taskdb' % os.environ))
        projectdb = Get(lambda : connect_database(
            'mysql+projectdb://%(MYSQL_PORT_3306_TCP_ADDR)s'
            ':%(MYSQL_PORT_3306_TCP_PORT)s/projectdb' % os.environ))
        resultdb = Get(lambda : connect_database(
            'mysql+resultdb://%(MYSQL_PORT_3306_TCP_ADDR)s'
            ':%(MYSQL_PORT_3306_TCP_PORT)s/resultdb' % os.environ))
    elif os.environ.get('MONGODB_NAME'):
        taskdb = Get(lambda : connect_database(
            'mongodb+taskdb://%(MONGODB_PORT_27017_TCP_ADDR)s'
            ':%(MONGODB_PORT_27017_TCP_PORT)s/taskdb' % os.environ))
        projectdb = Get(lambda : connect_database(
            'mongodb+projectdb://%(MONGODB_PORT_27017_TCP_ADDR)s'
            ':%(MONGODB_PORT_27017_TCP_PORT)s/projectdb' % os.environ))
        resultdb = Get(lambda : connect_database(
            'mongodb+resultdb://%(MONGODB_PORT_27017_TCP_ADDR)s'
            ':%(MONGODB_PORT_27017_TCP_PORT)s/resultdb' % os.environ))
    else:
        taskdb = Get(lambda : connect_database('sqlite+taskdb:///data/task.db'))
        projectdb = Get(lambda : connect_database('sqlite+projectdb:///data/project.db'))
        resultdb = Get(lambda : connect_database('sqlite+resultdb:///data/resultdb.db'))

    # queue
    if os.environ.get('RABBITMQ_NAME'):
        from pyspider.libs.rabbitmq import Queue
        amqp_url = ("amqp://guest:guest@%(RABBITMQ_PORT_5672_TCP_ADDR)s"
                    ":%(RABBITMQ_PORT_5672_TCP_PORT)s/%%2F" % os.environ)
        amqp = lambda name, Queue=Queue, amqp_url=amqp_url, queue_maxsize=queue_maxsize: \
                Queue(name, amqp_url=amqp_url, maxsize=queue_maxsize)
        newtask_queue = Get(lambda amqp=amqp: amqp("newtask_queue"))
        status_queue = Get(lambda amqp=amqp: amqp("status_queue"))
        scheduler2fetcher = Get(lambda amqp=amqp: amqp("scheduler2fetcher"))
        fetcher2processor = Get(lambda amqp=amqp: amqp("fetcher2processor"))
        processor2result = Get(lambda amqp=amqp: amqp("processor2result"))
    else:
        from multiprocessing import Queue
        newtask_queue = Queue(queue_maxsize)
        status_queue = Queue(queue_maxsize)
        scheduler2fetcher = Queue(queue_maxsize)
        fetcher2processor = Queue(queue_maxsize)
        processor2result = Queue(queue_maxsize)

    # scheduler_rpc
    if os.environ.get('SCHEDULER_NAME'):
        import xmlrpclib
        scheduler_rpc = Get(lambda xmlrpclib=xmlrpclib, scheduler_xmlrpc_port=scheduler_xmlrpc_port: \
                xmlrpclib.ServerProxy('http://%s:%s' % (
            os.environ['SCHEDULER_PORT_%d_TCP_ADDR' % scheduler_xmlrpc_port],
            os.environ['SCHEDULER_PORT_%d_TCP_PORT' % scheduler_xmlrpc_port]),
            allow_none=True))
    else:
        scheduler_rpc = None

    # phantomjs_proxy
    if os.environ.get('PHANTOMJS_NAME'):
        phantomjs_proxy = "%s:%s" % (
                os.environ['PHANTOMJS_PORT_%d_TCP_ADDR' % phantomjs_proxy_port],
                os.environ['PHANTOMJS_PORT_%d_TCP_PORT' % phantomjs_proxy_port]
                )
    else:
        phantomjs_proxy = None

# run commands ------------------------------------------
def run_scheduler(g=g):
    from pyspider.scheduler import Scheduler
    scheduler = Scheduler(taskdb=g.taskdb, projectdb=g.projectdb, resultdb=g.resultdb,
            newtask_queue=g.newtask_queue, status_queue=g.status_queue,
            out_queue=g.scheduler2fetcher)
    if g.demo_mode:
        scheduler.INQUEUE_LIMIT = 1000

    run_in_thread(scheduler.xmlrpc_run, port=g.scheduler_xmlrpc_port, bind=g.webui_host)
    scheduler.run()

def run_fetcher(g=g):
    from pyspider.fetcher.tornado_fetcher import Fetcher
    fetcher = Fetcher(inqueue=g.scheduler2fetcher, outqueue=g.fetcher2processor)
    fetcher.phantomjs_proxy = g.phantomjs_proxy

    run_in_thread(fetcher.xmlrpc_run, port=g.fetcher_xmlrpc_port, bind=g.webui_host)
    fetcher.run()

def run_processor(g=g):
    from pyspider.processor import Processor
    processor = Processor(projectdb=g.projectdb,
            inqueue=g.fetcher2processor, status_queue=g.status_queue,
            newtask_queue=g.newtask_queue, result_queue=g.processor2result)
    
    processor.run()

def run_result_worker(g=g):
    from pyspider.result import ResultWorker
    result_worker = ResultWorker(resultdb=g.resultdb, inqueue=g.processor2result)

    result_worker.run()

def run_webui(g=g):
    import cPickle as pickle

    from pyspider.fetcher.tornado_fetcher import Fetcher
    fetcher = Fetcher(inqueue=None, outqueue=None, async=False)
    fetcher.phantomjs_proxy = g.phantomjs_proxy

    from pyspider.webui.app import app
    app.config['taskdb'] = g.taskdb
    app.config['projectdb'] = g.projectdb
    app.config['resultdb'] = g.resultdb
    app.config['fetch'] = lambda x: fetcher.fetch(x)[1]
    app.config['scheduler_rpc'] = g.scheduler_rpc
    #app.config['cdn'] = '//cdnjs.cloudflare.com/ajax/libs/'
    if g.demo_mode:
        app.config['max_rate'] = 0.2
        app.config['max_burst'] = 3.0
    if 'WEBUI_USERNAME' in os.environ:
        app.config['webui_username'] = os.environ['WEBUI_USERNAME']
        app.config['webui_password'] = os.environ.get('WEBUI_PASSWORD', '')
    if not getattr(g, 'all_in_one', False):
        app.debug = g.debug
    app.run(host=g.webui_host, port=g.webui_port)

def all_in_one(g=g):
    import xmlrpclib
    g.scheduler_rpc = xmlrpclib.ServerProxy(
            'http://localhost:%d' % g.scheduler_xmlrpc_port)
    g.all_in_one = True

    if os.name == 'nt':
        run_in = run_in_thread
    else:
        run_in = run_in_subprocess

    threads = []
    threads.append(run_in(run_result_worker, g=g))
    threads.append(run_in(run_processor, g=g))
    threads.append(run_in(run_fetcher, g=g))
    threads.append(run_in(run_scheduler, g=g))
    threads.append(run_in(run_webui, g=g))

    while True:
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            break

    for each in threads:
        each.join()

if __name__ == '__main__':
    print "running with config:"
    for key in dir(g):
        if key.startswith("__"):
            continue
        print "%s=%r" % (key, getattr(g, key))

    if len(sys.argv) < 2:
        all_in_one(g)
    else:
        cmd = "run_"+sys.argv[1]
        locals()[cmd](g)
