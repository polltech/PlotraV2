import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';

const QueueListScreen = () => {
  const navigation = useNavigation();
  const [captures, setCaptures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, pending, synced, failed

  useEffect(() => {
    loadQueue();
  }, []);

  const loadQueue = async () => {
    try {
      // In real app, this would query local SQLite
      // For demo, show empty state
      setCaptures([]);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const filteredCaptures = captures.filter(c => {
    if (filter === 'all') return true;
    return c.status === filter;
  });

  const getStatusColor = (status) => {
    switch (status) {
      case 'synced': return '#4caf50';
      case 'pending': return '#ff9800';
      case 'failed': return '#f44336';
      default: return '#666';
    }
  };

  const renderCaptureItem = ({ item }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => {
        // Show details or retry if failed
        if (item.status === 'failed') {
          handleRetry(item.id);
        }
      }}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.farmId}>{item.farm_id || 'Unknown Farm'}</Text>
        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) + '20' }]}>
          <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>
            {item.status === 'synced' ? 'Synced' :
             item.status === 'pending' ? 'Pending' : 'Failed'}
          </Text>
        </View>
      </View>

      <View style={styles.cardBody}>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Area</Text>
          <Text style={styles.statValue}>
            {(item.area_hectares || 0).toFixed(2)} ha
          </Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Points</Text>
          <Text style={styles.statValue}>{item.points_count || 0}</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Saved</Text>
          <Text style={styles.statValue}>
            {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Text>
        </View>
      </View>

      {item.status === 'failed' && (
        <TouchableOpacity
          style={styles.retryButton}
          onPress={() => handleRetry(item.id)}
        >
          <Text style={styles.retryButtonText}>Retry →</Text>
        </TouchableOpacity>
      )}
    </TouchableOpacity>
  );

  const handleRetry = async (captureId) => {
    try {
      // URS: POST /api/v1/parcels/polygon/{id}/retry (or use batch)
      // For simplicity, we'll use the batch endpoint with single record
      const capture = captures.find(c => c.id === captureId);
      if (!capture) return;

      const response = await fetch(
        `http://192.168.100.5:8000/api/v1/parcels/polygon`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': 'plotra-prototype-key-2026',
          },
          body: JSON.stringify(capture),
        }
      );
      if (response.ok) {
        loadQueue();
        Alert.alert('Success', 'Retry submitted');
      } else {
        Alert.alert('Error', 'Retry failed');
      }
    } catch (e) {
      Alert.alert('Error', 'Network error');
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#6f4e37" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Queued records</Text>
        <Text style={styles.count}>{captures.length} records total</Text>
      </View>

      {/* Filter tabs */}
      <View style={styles.filterTabs}>
        {['all', 'pending', 'synced', 'failed'].map(f => (
          <TouchableOpacity
            key={f}
            style={[styles.filterTab, filter === f && styles.filterTabActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterTabText, filter === f && styles.filterTabTextActive]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <FlatList
        data={filteredCaptures}
        renderItem={renderCaptureItem}
        keyExtractor={item => `queue-${item.id}`}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyText}>No {filter === 'all' ? '' : filter} records found</Text>
          </View>
        }
      />

      <TouchableOpacity
        style={styles.fab}
        onPress={() => navigation.navigate('FarmIDEntry')}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 20,
    paddingTop: 60,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  count: {
    fontSize: 14,
    color: '#666',
  },
  filterTabs: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  filterTab: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 6,
  },
  filterTabActive: {
    backgroundColor: '#6f4e37',
  },
  filterTabText: {
    fontSize: 12,
    color: '#666',
    fontWeight: '500',
  },
  filterTabTextActive: {
    color: '#fff',
  },
  list: {
    padding: 16,
    paddingBottom: 80,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
   padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  farmId: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  cardBody: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stat: {
    alignItems: 'center',
  },
  statLabel: {
    fontSize: 11,
    color: '#999',
    marginBottom: 2,
  },
  statValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  retryButton: {
    marginTop: 12,
    alignItems: 'flex-end',
  },
  retryButtonText: {
    fontSize: 14,
    color: '#6f4e37',
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    marginTop: 60,
  },
  emptyIcon: {
    fontSize: 60,
    marginBottom: 16,
  },
  emptyText: {
    fontSize: 16,
    color: '#999',
  },
  fab: {
    position: 'absolute',
    right: 20,
    bottom: 30,
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#6f4e37',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 8,
  },
  fabText: {
    fontSize: 32,
    color: '#fff',
    marginTop: -2,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});

export default QueueListScreen;
