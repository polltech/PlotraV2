import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:location/location.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../models/farm.dart';
import '../models/latlng_data.dart';
import '../services/auth_service.dart';

class FarmMapScreen extends StatefulWidget {
  final Farm? existingFarm;
  
  const FarmMapScreen({super.key, this.existingFarm});

  @override
  State<FarmMapScreen> createState() => _FarmMapScreenState();
}

class _FarmMapScreenState extends State<FarmMapScreen>
    with SingleTickerProviderStateMixin {
  
  final MapController _mapController = MapController();
  List<LatLng> _points = [];
  bool _isDrawing = false;
  bool _isLoading = false;
  Position? _currentPosition;
  String _farmName = '';
  
  late AnimationController _fabAnimationController;
  late Animation<double> _fabScaleAnimation;

  // Kenya default center (Nairobi)
  static const LatLng _defaultCenter = LatLng(-1.2921, 36.8219);
  static const double _defaultZoom = 14.0;

  @override
  void initState() {
    super.initState();
    
    _fabAnimationController = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );
    _fabScaleAnimation = Tween<double>(begin: 1.0, end: 0.95).animate(
      CurvedAnimation(parent: _fabAnimationController, curve: Curves.easeInOut),
    );

    if (widget.existingFarm != null) {
      _farmName = widget.existingFarm!.name;
      _points = widget.existingFarm!.polygon
          .map((p) => LatLng(p.latitude, p.longitude))
          .toList();
    } else {
      _farmName = 'Farm ${DateTime.now().millisecondsSinceEpoch ~/ 1000}';
    }
    
    _getCurrentLocation();
  }

  @override
  void dispose() {
    _fabAnimationController.dispose();
    super.dispose();
  }

  Future<void> _getCurrentLocation() async {
    setState(() => _isLoading = true);

    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() => _isLoading = false);
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          setState(() => _isLoading = false);
          return;
        }
      }

      if (permission == LocationPermission.deniedForever) {
        setState(() => _isLoading = false);
        return;
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      setState(() {
        _currentPosition = position;
        _isLoading = false;
      });

      _mapController.move(
        LatLng(position.latitude, position.longitude),
        _defaultZoom,
      );
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  void _onMapTap(LatLng point) {
    if (!_isDrawing) return;
    
    setState(() {
      _points.add(point);
    });
    _fabAnimationController.forward().then((_) {
      _fabAnimationController.reverse();
    });
  }

  void _clearPoints() {
    setState(() {
      _points.clear();
    });
  }

  Future<void> _saveFarm() async {
    if (_points.length < 3) {
      _showErrorSnackBar('Please draw at least 3 points to create a polygon.');
      return;
    }

    setState(() => _isLoading = true);

    try {
      final auth = Provider.of<AuthService>(context, listen: false);
      final api = ApiService();
      await api.init(); // Ensure token is set

      final farm = Farm(
        id: widget.existingFarm?.id ?? '',
        name: _farmName,
        polygon: _points
            .map((p) => LatLngData(latitude: p.latitude, longitude: p.longitude))
            .toList(),
        area: _calculateArea(_points),
        status: widget.existingFarm?.status ?? 'draft',
        createdAt: widget.existingFarm?.createdAt ?? DateTime.now(),
        updatedAt: DateTime.now(),
      );

      Farm savedFarm;
      if (widget.existingFarm != null) {
        savedFarm = await api.updateFarm(farm.id, farm);
      } else {
        savedFarm = await api.createFarm(farm);
      }

      setState(() => _isLoading = false);

      if (mounted) {
        _showSuccessSnackBar('Farm saved successfully!');
        await Future.delayed(const Duration(seconds: 1));
        Navigator.pop(context, savedFarm);
      }
    } catch (e) {
      setState(() => _isLoading = false);
      _showErrorSnackBar('Failed to save farm: $e');
    }
  }

  double _calculateArea(List<LatLng> points) {
    if (points.length < 3) return 0.0;
    
    // Shoelace formula
    double area = 0.0;
    for (int i = 0; i < points.length; i++) {
      int j = (i + 1) % points.length;
      area += points[i].latitude * points[j].longitude;
      area -= points[j].latitude * points[i].longitude;
    }
    return (area.abs() / 2) * 111139 * 111139 / 10000; // Convert to hectares
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline, color: Colors.white),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.red.shade900,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        margin: const EdgeInsets.all(20),
      ),
    );
  }

  void _showSuccessSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle, color: Colors.white),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.green.shade900,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        margin: const EdgeInsets.all(20),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0a0a0a),
      appBar: AppBar(
        title: Text(
          _isDrawing ? 'Draw Farm Boundary' : 'Map Your Farm',
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
        backgroundColor: const Color(0xFF0a0a0a),
        elevation: 0,
        actions: [
          // Draw mode toggle
          IconButton(
            icon: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: _isDrawing 
                    ? const Color(0xFFd4a853).withOpacity(0.2)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: _isDrawing 
                      ? const Color(0xFFd4a853)
                      : const Color(0xFF333333),
                ),
              ),
              child: Icon(
                Icons.edit,
                color: _isDrawing ? const Color(0xFFd4a853) : Colors.white,
                size: 20,
              ),
            ),
            onPressed: () {
              setState(() => _isDrawing = !_isDrawing);
            },
            tooltip: _isDrawing ? 'Cancel Drawing' : 'Start Drawing',
          ),
          if (_points.isNotEmpty)
            IconButton(
              icon: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.red),
                ),
                child: const Icon(Icons.clear, color: Colors.red, size: 20),
              ),
              onPressed: _clearPoints,
              tooltip: 'Clear Points',
            ),
        ],
      ),
      
      body: Stack(
        children: [
          // Map
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              center: _currentPosition != null
                  ? LatLng(_currentPosition!.latitude, _currentPosition!.longitude)
                  : _defaultCenter,
              zoom: _defaultZoom,
              minZoom: 10,
              maxZoom: 18,
              onTap: (_, point) => _onMapTap(point),
              interactiveFlags: InteractiveFlag.all,
              plugins: [],
            ),
            children: [
              // Tile Layer
              TileLayer(
                urlTemplate: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                subdomains: const ['a', 'b', 'c'],
                userAgentPackageName: 'ai.plotra.app',
                tileProvider: const TileProvider.network(),
              ),
              
              // Polygon layer
              if (_points.isNotEmpty)
                PolygonLayer(
                  polygons: [
                    Polygon(
                      points: _points,
                      color: const Color(0xFFd4a853).withOpacity(0.3),
                      borderStrokeWidth: 3,
                      borderColor: const Color(0xFFd4a853),
                      disableHolesDetection: true,
                    ),
                  ],
                ),
              
              // Points markers
              MarkerLayer(
                markers: _points
                    .map((point) => Marker(
                          point: point,
                          width: 30,
                          height: 30,
                          child: AnimatedScale(
                            scale: 1.0,
                            duration: const Duration(milliseconds: 100),
                            child: Container(
                              decoration: BoxDecoration(
                                color: const Color(0xFFd4a853),
                                shape: BoxShape.circle,
                                border: Border.all(color: Colors.white, width: 2),
                                boxShadow: [
                                  BoxShadow(
                                    color: const Color(0xFFd4a853).withOpacity(0.5),
                                    blurRadius: 8,
                                    offset: const Offset(0, 2),
                                  ),
                                ],
                              ),
                              child: const Icon(
                                Icons.location_on,
                                color: Colors.black,
                                size: 20,
                              ),
                            ),
                          ),
                        ))
                    .toList(),
              ),

              // Current location marker
              if (_currentPosition != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: LatLng(
                        _currentPosition!.latitude,
                        _currentPosition!.longitude,
                      ),
                      width: 50,
                      height: 50,
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.blue.withOpacity(0.3),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.blue, width: 2),
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.my_location,
                            color: Colors.blue,
                            size: 20,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
            ],
          ),

          // Loading overlay
          if (_isLoading)
            Container(
              color: Colors.black.withOpacity(0.7),
              child: const Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(
                        Color(0xFFd4a853),
                      ),
                    ),
                    SizedBox(height: 20),
                    Text(
                      'Saving farm...',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // Drawing mode indicator
          if (_isDrawing && !_isLoading)
            Positioned(
              top: 16,
              left: 20,
              right: 20,
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(0.85),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFd4a853), width: 1),
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.edit,
                      color: Color(0xFFd4a853),
                      size: 20,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Drawing Mode Active',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 14,
                            ),
                          ),
                          Text(
                            'Points: ${_points.length}',
                            style: const TextStyle(
                              color: Color(0xFF8a8a8a),
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: () {
                        setState(() => _isDrawing = false);
                      },
                      child: const Text(
                        'Cancel',
                        style: TextStyle(color: Colors.red),
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // Area indicator
          if (_points.length >= 3 && !_isLoading)
            Positioned(
              bottom: 120,
              left: 20,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFFd4a853), Color(0xFFe8c97a)],
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFFd4a853).withOpacity(0.3),
                      blurRadius: 10,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                  const Text(
                    'Farm Area',
                    style: TextStyle(
                      color: Colors.black87,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${_calculateArea(_points).toStringAsFixed(2)} ha',
                    style: const TextStyle(
                      color: Colors.black87,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
      
      // Bottom action bar
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFF0a0a0a),
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          border: Border.all(color: const Color(0xFF1a1a1a)),
        ),
        child: SafeArea(
          child: Row(
            children: [
              // Farm name text field
              Expanded(
                child: TextFormField(
                  initialValue: _farmName,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: 'Farm Name',
                    labelStyle: const TextStyle(color: Color(0xFF8a8a8a), fontSize: 12),
                    filled: true,
                    fillColor: const Color(0xFF1a1a1a),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFF333333)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFd4a853), width: 2),
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                  ),
                  onChanged: (value) => _farmName = value,
                ),
              ),
              const SizedBox(width: 12),
              
              // Save button
              AnimatedBuilder(
                animation: _fabScaleAnimation,
                builder: (context, child) {
                  return Transform.scale(
                    scale: _fabScaleAnimation.value,
                    child: FloatingActionButton(
                      onPressed: _points.length >= 3 ? _saveFarm : null,
                      backgroundColor: const Color(0xFFd4a853),
                      foregroundColor: Colors.black,
                      child: _isLoading
                          ? const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  Colors.black,
                                ),
                              ),
                            )
                          : const Icon(Icons.save, size: 24),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
