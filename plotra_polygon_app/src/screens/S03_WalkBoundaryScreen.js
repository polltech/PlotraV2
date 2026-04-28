import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  Alert,
} from 'react-native';
import MapView, { Polygon, Circle, Marker, Polyline } from 'react-native-maps';
import * as Location from 'expo-location';
import { useRoute, useNavigation } from '@react-navigation/native';
import * as turf from '@turf/turf';

const WalkBoundaryScreen = () => {
  const route = useRoute();
  const navigation = useNavigation();
  const { farmId, farm } = route.params || {};

  const [currentLocation, setCurrentLocation] = useState(null);
  const [markers, setMarkers] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [polygonCoords, setPolygonCoords] = useState([]);
  const [accuracy, setAccuracy] = useState(null);
  const [topologyError, setTopologyError] = useState(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const mapRef = useRef(null);

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission required', 'Location permission is needed for boundary capture');
        return;
      }

      const locationSubscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.High,
          timeInterval: 1000,
          distanceInterval: 1,
        },
        (loc) => {
          setCurrentLocation(loc);
          setAccuracy(loc.coords.accuracy);
        }
      );

      return () => locationSubscription.remove();
    })();
  }, []);

  // Validate polygon topology when we have 4+ points
  useEffect(() => {
    if (polygonCoords.length >= 4) {
      validatePolygon();
    } else {
      setTopologyError(null);
    }
  }, [polygonCoords]);

  const validatePolygon = () => {
    setIsCalculating(true);
    try {
      // Build polygon (first point must repeat at end for closure)
      const coordsForTurf = [
        ...polygonCoords.map(p => [p.longitude, p.latitude]),
        [polygonCoords[0].longitude, polygonCoords[0].latitude] // close ring
      ];

      const polygon = turf.polygon([coordsForTurf]);

      // Check validity
      const valid = turf.booleanValid(polygon);
      if (!valid) {
        setTopologyError('Boundary geometry is invalid. Please re-walk.');
        return;
      }

      // Check self-intersection
      const intersects = turf.kinks(polygon);
      if (intersects.features.length > 0) {
        setTopologyError('Boundary lines cross. Walk in one direction without backtracking.');
        return;
      }

      // Check area (minimum 0.1 ha)
      const area = turf.area(polygon); // m²
      const hectares = area / 10000;
      if (hectares < 0.1) {
        setTopologyError('Polygon too small (min 0.1 ha).');
        return;
      }

      setTopologyError(null);
    } catch (e) {
      setTopologyError('Validation error: ' + e.message);
    } finally {
      setIsCalculating(false);
    }
  };

  const handleMapPress = (event) => {
    if (!isRecording) return;

    const { coordinate } = event.nativeEvent;
    // Check minimum distance between points (5m)
    if (markers.length > 0) {
      const last = markers[markers.length - 1];
      const dist = calculateDistance(last, coordinate);
      if (dist < 5) {
        Alert.alert('Too close', 'Points must be at least 5m apart');
        return;
      }
    }

    const newMarker = {
      id: Date.now().toString(),
      coordinate,
      timestamp: new Date().toISOString(),
    };

    const newMarkers = [...markers, newMarker];
    setMarkers(newMarkers);
    setPolygonCoords(newMarkers.map(m => m.coordinate));
  };

  const calculateDistance = (p1, p2) => {
    // Approximate distance in meters using haversine
    const R = 6371000; // Earth radius in m
    const φ1 = (p1.latitude * Math.PI) / 180;
    const φ2 = (p2.latitude * Math.PI) / 180;
    const Δφ = ((p2.latitude - p1.latitude) * Math.PI) / 180;
    const Δλ = ((p2.longitude - p1.longitude) * Math.PI) / 180;

    const a =
      Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
      Math.cos(φ1) * Math.cos(φ2) *
      Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  };

  const handleUndo = () => {
    if (markers.length === 0) return;
    const newMarkers = markers.slice(0, -1);
    setMarkers(newMarkers);
    setPolygonCoords(newMarkers.map(m => m.coordinate));
  };

  const handleClear = () => {
    setMarkers([]);
    setPolygonCoords([]);
    setTopologyError(null);
  };

  const handleContinue = () => {
    if (polygonCoords.length < 4) {
      Alert.alert('Not enough points', 'At least 4 points required to form a closed boundary');
      return;
    }

    if (topologyError) {
      Alert.alert('Topology error', 'Please fix boundary errors before continuing');
      return;
    }

    // Calculate area
    const coordsForTurf = [
      polygonCoords.map(p => [p.longitude, p.latitude]),
      [polygonCoords[0].longitude, polygonCoords[0].latitude]
    ];
    const polygon = turf.polygon(coordsForTurf);
    const areaSqM = turf.area(polygon);
    const hectares = areaSqM / 10000;

    // Calculate perimeter
    const perimeter = turf.length(polygon, { units: 'meters' });

    navigation.navigate('ReviewPolygon', {
      farmId,
      farm,
      polygonCoords,
      areaHectares: hectares,
      perimeterMeters: perimeter,
      pointsCount: polygonCoords.length,
    });
  };

  const renderPolygon = () => {
    if (polygonCoords.length < 3) return null;

    const polygonCoordsClosed = [
      ...polygonCoords.map(p => ({ latitude: p.latitude, longitude: p.longitude })),
      polygonCoords[0] // close
    ];

    return (
      <Polygon
        coordinates={polygonCoordsClosed}
        strokeColor="#6f4e37"
        fillColor="rgba(111, 78, 55, 0.3)"
        strokeWidth={2}
      />
    );
  };

  return (
    <View style={styles.container}>
      {/* Map */}
      <MapView
        ref={mapRef}
        style={styles.map}
        initialRegion={
          currentLocation
            ? {
                latitude: currentLocation.coords.latitude,
                longitude: currentLocation.coords.longitude,
                latitudeDelta: 0.005,
                longitudeDelta: 0.005,
              }
            : undefined
        }
        showsUserLocation
        followsUserLocation
        onPress={handleMapPress}
      >
        {renderPolygon()}
        {markers.map((marker) => (
          <Marker
            key={marker.id}
            coordinate={marker.coordinate}
            title={`Point ${markers.indexOf(marker) + 1}`}
          />
        ))}
      </MapView>

      {/* Top Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>
          Walk boundary {farmId && `· ${farmId}`}
        </Text>
        <View style={{ width: 60 }} />
      </View>

      {/* GPS Accuracy Indicator */}
      {accuracy && (
        <View style={styles.accuracyBar}>
          <View
            style={[
              styles.accuracyDot,
              accuracy <= 5 ? styles.accuracyExcellent :
              accuracy <= 10 ? styles.accuracyGood :
              accuracy <= 30 ? styles.accuracyFair : styles.accuracyPoor
            ]}
          />
          <Text style={styles.accuracyText}>
            GPS accuracy: {accuracy.toFixed(1)} m
          </Text>
        </View>
      )}

      {/* Topology Error */}
      {topologyError && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorIcon}>✕</Text>
          <View style={styles.errorContent}>
            <Text style={styles.errorTitle}>Boundary lines cross</Text>
            <Text style={styles.errorTextSmall}>{topologyError}</Text>
          </View>
          <TouchableOpacity onPress={handleUndo} style={styles.undoButton}>
            <Text style={styles.undoButtonText}>Undo last</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={handleClear} style={styles.clearButton}>
            <Text style={styles.clearButtonText}>Clear all</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Bottom Controls */}
      <View style={styles.controls}>
        <View style={styles.stats}>
          <Text style={styles.statsText}>
            Points marked: {markers.length} (min 4 required ✓)
          </Text>
        </View>

        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.sideButton, markers.length === 0 && styles.buttonDisabled]}
            onPress={handleUndo}
            disabled={markers.length === 0}
          >
            <Text style={styles.sideButtonText}>Undo last</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.captureButton, !isRecording && styles.captureButtonInactive]}
            onPress={() => setIsRecording(!isRecording)}
          >
            <Text style={styles.captureButtonText}>
              {isRecording ? '● Mark point here' : '+ Mark point here'}
            </Text>
          </TouchableOpacity>
        </View>

        {markers.length >= 4 && !topologyError && (
          <TouchableOpacity style={styles.saveButton} onPress={handleContinue}>
            <Text style={styles.saveButtonText}>Save polygon ›</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  map: {
    flex: 1,
  },
  topBar: {
    position: 'absolute',
    top: 60,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    backgroundColor: 'rgba(255,255,255,0.9)',
    paddingVertical: 12,
  },
  backText: {
    fontSize: 18,
    color: '#6f4e37',
    fontWeight: '600',
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  accuracyBar: {
    position: 'absolute',
    top: 130,
    left: 16,
    right: 16,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.95)',
    padding: 10,
    borderRadius: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  accuracyDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 8,
  },
  accuracyExcellent: { backgroundColor: '#4caf50' },
  accuracyGood: { backgroundColor: '#8bc34a' },
  accuracyFair: { backgroundColor: '#ff9800' },
  accuracyPoor: { backgroundColor: '#f44336' },
  accuracyText: {
    fontSize: 13,
    color: '#333',
    fontWeight: '500',
  },
  errorBanner: {
    position: 'absolute',
    top: 190,
    left: 16,
    right: 16,
    backgroundColor: '#ffebee',
    borderLeftWidth: 4,
    borderLeftColor: '#f44336',
    padding: 12,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  errorIcon: {
    fontSize: 20,
    color: '#f44336',
    marginRight: 8,
  },
  errorContent: {
    flex: 1,
  },
  errorTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#c62828',
    marginBottom: 2,
  },
  errorTextSmall: {
    fontSize: 12,
    color: '#666',
  },
  undoButton: {
    marginLeft: 8,
    padding: 6,
  },
  undoButtonText: {
    fontSize: 12,
    color: '#6f4e37',
    fontWeight: '600',
  },
  clearButton: {
    marginLeft: 4,
    padding: 6,
  },
  clearButtonText: {
    fontSize: 12,
    color: '#f44336',
    fontWeight: '600',
  },
  controls: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(255,255,255,0.98)',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 16,
    paddingBottom: 30,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 5,
  },
  stats: {
    marginBottom: 12,
  },
  statsText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
  },
  sideButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#6f4e37',
    alignItems: 'center',
  },
  buttonDisabled: {
    borderColor: '#ccc',
    opacity: 0.5,
  },
  sideButtonText: {
    color: '#6f4e37',
    fontWeight: '600',
  },
  captureButton: {
    flex: 2,
    backgroundColor: '#4caf50',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  captureButtonInactive: {
    backgroundColor: '#ccc',
  },
  captureButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  saveButton: {
    marginTop: 12,
    backgroundColor: '#6f4e37',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  saveButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default WalkBoundaryScreen;
