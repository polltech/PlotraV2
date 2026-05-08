<?php

/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the installation.
 * You don't have to use the website, you can copy this file to "wp-config.php"
 * and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * Database settings
 * * Secret keys
 * * Database table prefix
 * * ABSPATH
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/
 *
 * @package WordPress
 */

// ** Database settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define( 'DB_NAME', 'orderifi_wp283' );

/** Database username */
define( 'DB_USER', 'orderifi_wp283' );

/** Database password */
define( 'DB_PASSWORD', '7fT!5SCp]7' );

/** Database hostname */
define( 'DB_HOST', 'wordpress-db' );

/** Database charset to use in creating database tables. */
define( 'DB_CHARSET', 'utf8mb4' );

/** The database collate type. Don't change this if in doubt. */
define( 'DB_COLLATE', '' );

/**#@+
 * Authentication unique keys and salts.
 *
 * Change these to different unique phrases! You can generate these using
 * the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}.
 *
 * You can change these at any point in time to invalidate all existing cookies.
 * This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define( 'AUTH_KEY',         'krmbbqunci6zivij7iwbmeomab8hax7dhknijlryi8mch6v2ehqwfh4iyomd7gyd' );
define( 'SECURE_AUTH_KEY',  'rftk3ewbzriozh7wkpqalgs2uttdh0pxqp4c8mfjbk6giph8pfoze5rmuyfyepob' );
define( 'LOGGED_IN_KEY',    '7kf30iowrkucr1ds6gmxdnwy9ldahrsgot0wuvqatpnp9owz1konigphkuamogig' );
define( 'NONCE_KEY',        'ckipv9hmknjvtlsejzszabndohmad1zyspnjtvgccfia8w8m0ewtorduwkmur16d' );
define( 'AUTH_SALT',        'rmskyhzuzqgp47ysd4he2qk0slnamk8ioqgmnq0z9vrvft0xuktkvezcnhmg5ub7' );
define( 'SECURE_AUTH_SALT', 'ferbslajtzbqheqeozumtvwdwj8are6cjyi2jnuvveaivuazwcervrf7ahhn2qhc' );
define( 'LOGGED_IN_SALT',   'tshgkmgjpl6hak5gi0vkdprftos5qmkbopx3njt1z5ufz66ttnxa8l3btxam0a5b' );
define( 'NONCE_SALT',       'jcdovdzb4kszsvt2svkggawvbeagkcpky3maqkq9lh9qfcg8lm11evnuckwmz67i' );

/**#@-*/

/**
 * WordPress database table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 *
 * At the installation time, database tables are created with the specified prefix.
 * Changing this value after WordPress is installed will make your site think
 * it has not been installed.
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/#table-prefix
 */
$table_prefix = 'wp1k_';

/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the documentation.
 *
 * @link https://developer.wordpress.org/advanced-administration/debug/debug-wordpress/
 */
define( 'WP_DEBUG', false );

/* Add any custom values between this line and the "stop editing" line. */

/* That's all, stop editing! Happy publishing. */

/** Absolute path to the WordPress directory. */
if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/** Sets up WordPress vars and included files. */
require_once ABSPATH . 'wp-settings.php';
