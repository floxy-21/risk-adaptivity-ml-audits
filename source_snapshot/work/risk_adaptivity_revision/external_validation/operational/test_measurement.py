"""Offline instrumentation checks; these are NOT measured service outcomes."""
import gzip
import unittest
from measurement import HTTPRecorder,hpm_range_url,summarize_trial


class Reply:
    status=200
    will_close=False
    def read(self):return gzip.compress(b'[[1,2.0],[2,3.0]]',mtime=0)
    def getheaders(self):return [('Content-Encoding','gzip'),('Age','3')]


class Connection:
    instances=[]
    def __init__(self,host,timeout):self.calls=[];self.instances.append(self)
    def request(self,method,path,headers):self.calls.append((method,path,headers))
    def getresponse(self):return Reply()
    def close(self):pass


class Tests(unittest.TestCase):
    def test_payload_bytes_persistent_connection_and_cap(self):
        Connection.instances.clear()
        recorder=HTTPRecorder(['heatpumpmonitor.org'],maximum_requests=2,min_start_interval=0,connection_factory=Connection)
        url=hpm_range_url(2,'heatpump_elec_kwh','2025-01-01','2025-01-02',3600)
        for i in (1,2):
            response=recorder.get(url,trial_id='offline',policy='fixture',role='unit-test',information_round=i)
            self.assertEqual(response.payload,b'[[1,2.0],[2,3.0]]')
            self.assertEqual(response.observation['decoded_payload_bytes'],len(response.payload))
            self.assertEqual(response.observation['response_body_bytes'],len(Reply().read()))
        self.assertEqual(len(Connection.instances),1)
        self.assertEqual(len(Connection.instances[0].calls),2)
        with self.assertRaises(RuntimeError):recorder.get(url,trial_id='offline',policy='fixture',role='unit-test',information_round=3)
        result=summarize_trial(recorder.records,elapsed_seconds=0,planning_seconds=0,validation_seconds=0,requested_timestamps=[1,2],returned_timestamps=[1,2],precision_success=True)
        self.assertEqual((result['requests'],result['information_rounds'],result['distinct_returned_samples']),(2,2,2))
    def test_public_read_only_guard(self):
        recorder=HTTPRecorder(['heatpumpmonitor.org'],connection_factory=Connection)
        for url in ['http://heatpumpmonitor.org/x','https://private.invalid/x','https://heatpumpmonitor.org/x?apikey=secret']:
            with self.assertRaises(ValueError):recorder.get(url,trial_id='offline',policy='fixture',role='unit-test',information_round=1)
        self.assertEqual(recorder.records,[])


if __name__=='__main__':unittest.main()
