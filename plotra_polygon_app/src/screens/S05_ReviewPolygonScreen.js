import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  Alert,
  Image,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';

const ReviewPolygonScreen = () => {
  const route = useRoute();
  const navigation = useNavigation();
  const {
    farmId,
    farm,
    polygonCoords,
    areaHectares,
    perimeterMeters,
    pointsCount,
  } = route.params;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    // Check connectivity (simplified)
    // In real app use NetInfo
  }, []);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const boundaryGeoJSON = {
        type: "Polygon",
        coordinates: [[
          ...polygonCoords.map(p => [p.longitude, p.latitude]),
          [polygonCoords[0].longitude, polygonCoords[0].latitude] // close ring
        ]]
      };

      // Capture device ID
      const [deviceId, deviceModel] = [
        await AsyncStorage.getItemAsync('device_id') || `android-${Date.now()}`,
        'Android',
      ];
      await AsyncStorage.setItemAsync('device_id', deviceId);

      // Get mean GPS accuracy from session (approximate)
      const gpsAccuracyAvg = 5.0; // Would track this during walk

      const payload = {
        farm_id: parseInt(farmId),
        parcel_name: farm?.farm_name || `Parcel ${Date.now()}`,
        boundary_geojson: boundaryGeoJSON,
        area_hectares: areaHectares,
        perimeter_meters: perimeterMeters,
        points_count: pointsCount,
        captured_at: new Date().toISOString(),
        device_id: deviceId,
        device_info: {
          model: deviceModel,
          app_version: '1.0.0'
        },
        notes: 'Captured via mobile polygon walk',
        gps_accuracy_avg: gpsAccuracyAvg,
        agent_id: null, // Optional per URS
      };

      // Try to submit to URS API (v1) with API key
      const response = await fetch(
        'http://192.168.100.5:8000/api/v1/parcels/polygon',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': 'plotra-prototype-key-2026',
          },
          body: JSON.stringify(payload),
        }
      );

      if (response.ok) {
        const result = await response.json();
        navigation.replace('Submitted', {
          captureId: result.id,
          farmId,
          area: areaHectares,
          points: pointsCount,
          status: 'synced'
        });
      } else {
        throw new Error('Server error: ' + response.status);
      }
    } catch (error) {
      console.error('Submit error:', error);
      // Save offline (this would call dbService.savePolygonCapture)
      navigation.replace('OfflineSaved', {
        farmId,
        polygonCoords,
        areaHectares,
        perimeterMeters,
        pointsCount,
        error: error.message,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Review polygon</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={styles.content}>
        {/* Area Display */}
        <View style={styles.areaCard}>
          <Text style={styles.areaValue}>{areaHectares.toFixed(4)}</Text>
          <Text style={styles.areaLabel}>hectares — calculated area</Text>
        </View>

        {/* Stats */}
        <View style={styles.statsCard}>
          <View style={styles.statItem}>
            <Text style={styles.statLabel}>Points</Text>
            <Text style={styles.statValue}>{pointsCount} coords</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statLabel}>Perimeter</Text>
            <Text style={styles.statValue}>{perimeterMeters?.toFixed(1)} m</Text>
          </View>
        </View>

        {/* Farm Info */}
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>{farm?.farm_name || `Farm ${farmId}`}</Text>
          <Text style={styles.infoSub}>{farmId} — {farm?.cooperative_name || 'Unknown cooperative'}</Text>
        </View>

        {/* Map Preview (static) */}
        <View style={styles.mapPreview}>
          <Text style={styles.mapPlaceholder}>
            [Map preview with polygon would show here]
          </Text>
          <Text style={styles.mapNote}>
            Open in full screen to verify boundary
          </Text>
        </View>

        {/* Submit Button */}
        <TouchableOpacity
          style={[styles.submitButton, isSubmitting && styles.buttonDisabled]}
          onPress={handleSubmit}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Text style={styles.submitButtonText}>Submit to Plotra →</Text>
              <Text style={styles.submitButtonSub}>Capture another farm</Text>
            </>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.secondaryButtonText}>Re-walk boundary</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingTop: 60,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  backText: {
    fontSize: 18,
    color: '#6f4e37',
    fontWeight: '600',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  areaCard: {
    backgroundColor: '#fff',
    padding: 24,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  areaValue: {
    fontSize: 36,
    fontWeight: 'bold',
    color: '#6f4e37',
  },
  areaLabel: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  statsCard: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 12,
    flexDirection: 'row',
    marginBottom: 16,
    justifyContent: 'space-around',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statItem: {
    alignItems: 'center',
    flex: 1,
  },
  statLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  statValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  statDivider: {
    width: 1,
    backgroundColor: '#e0e0e0',
  },
  infoCard: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  infoTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  infoSub: {
    fontSize: 14,
    color: '#666',
  },
  mapPreview: {
    height: 200,
    backgroundColor: '#e3f2fd',
    borderRadius: 12,
    marginBottom: 16,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#bbdefb',
    borderStyle: 'dashed',
  },
  mapPlaceholder: {
    fontSize: 14,
    color: '#1976d2',
    fontStyle: 'italic',
  },
  mapNote: {
    fontSize: 12,
    color: '#666',
    marginTop: 8,
  },
  submitButton: {
    backgroundColor: '#4caf50',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
  },
  buttonDisabled: {
    backgroundColor: '#ccc',
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  submitButtonSub: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  secondaryButton: {
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#6f4e37',
  },
  secondaryButtonText: {
    color: '#6f4e37',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default ReviewPolygonScreen;
